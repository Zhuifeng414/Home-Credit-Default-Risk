#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jul 13 23:17:57 2018

@author: Kazuki
"""


import gc, os
from tqdm import tqdm
import pandas as pd
import sys
sys.path.append(f'/home/{os.environ.get("USER")}/PythonLibrary')
import lgbextension as ex
import lightgbm as lgb
from multiprocessing import cpu_count
#from glob import glob
from sklearn.model_selection import GroupKFold
import count
import utils_cat
import utils
utils.start(__file__)
#==============================================================================

NFOLD = 5

SEED = 71

param = {
         'objective': 'binary',
         'metric': 'auc',
         'learning_rate': 0.02,
         'max_depth': 6,
         'num_leaves': 63,
         'max_bin': 255,
         
         'min_child_weight': 10,
         'min_data_in_leaf': 150,
         'reg_lambda': 0.5,  # L2 regularization term on weights.
         'reg_alpha': 0.5,  # L1 regularization term on weights.
         
         'colsample_bytree': 0.9,
         'subsample': 0.9,
#         'nthread': 32,
         'nthread': cpu_count(),
         'bagging_freq': 1,
         'verbose':-1,
         'seed': SEED
         }



use_files = []


# =============================================================================
# load train
# =============================================================================

files = utils.get_use_files(use_files, True)

X_train = pd.concat([
                pd.read_feather(f) for f in tqdm(files, mininterval=60)
               ], axis=1)
y_train = utils.read_pickles('../data/prev_label').TARGET


if X_train.columns.duplicated().sum()>0:
    raise Exception(f'duplicated!: { X_train.columns[X_train.columns.duplicated()] }')
print('no dup :) ')
print(f'X_train.shape {X_train.shape}')

gc.collect()

sub_train = utils.read_pickles('../data/prev_train', ['SK_ID_CURR', 'SK_ID_PREV']).set_index('SK_ID_CURR')
sub_train['y'] = y_train.values
sub_train['cnt'] = sub_train.index.value_counts()
sub_train['w'] = 1 / sub_train.cnt.values

group_kfold = GroupKFold(n_splits=NFOLD)
sub_train['g'] = sub_train.index % NFOLD

CAT = list( set(X_train.columns)&set(utils_cat.ALL))



# =============================================================================
# load test
# =============================================================================
files = utils.get_use_files(use_files, False)

X_test = pd.concat([
                pd.read_feather(f) for f in tqdm(files, mininterval=60)
               ], axis=1)

sub_test = utils.read_pickles('../data/prev_test', ['SK_ID_CURR', 'SK_ID_PREV']).set_index('SK_ID_CURR')

# =============================================================================
# predict
# =============================================================================
sub_train['y_pred'] = 0
sub_test['y_pred'] = 0

sub_train.reset_index(inplace=True)
sub_test.reset_index(inplace=True)

for train_index, valid_index in group_kfold.split(X_train, sub_train.y, sub_train.g):
    dtrain = lgb.Dataset(X_train.iloc[train_index], sub_train.iloc[train_index].y,
                         categorical_feature=CAT)
    dvalid = lgb.Dataset(X_train.iloc[valid_index], sub_train.iloc[valid_index].y,
                         categorical_feature=CAT)
    
    model = lgb.train(params=param, train_set=dtrain, num_boost_round=9999, 
                  valid_sets=[dtrain, dvalid], 
                  valid_names=['train','valid'], 
                  early_stopping_rounds=100, 
                  #evals_result=evals_result, 
                  verbose_eval=50
                  )
    
    sub_train.iloc[valid_index, -1] = model.predict(X_train.iloc[valid_index])
    sub_test['y_pred'] += model.predict(X_test)

sub_test['y_pred'] /= NFOLD

print('train:', sub_train.y_pred.describe())
print('test:', sub_test.y_pred.describe())
# =============================================================================
# save
# =============================================================================

sub_train.to_feather('../data/prev_train_imputation.f')
sub_test.to_feather('../data/prev_test_imputation.f')



#==============================================================================
utils.end(__file__)


