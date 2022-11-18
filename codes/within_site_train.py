import time
import math
import os.path
import pickle
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import zscore

import xgboost as xgb
from skrvm import RVR
from glmnet import ElasticNet
from brainage import XGBoostAdapted
from brainage import stratified_splits

import sklearn.gaussian_process as gp
from sklearn.kernel_ridge import KernelRidge
from sklearn.decomposition import PCA
from sklearn.feature_selection import VarianceThreshold
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.metrics import mean_absolute_error, mean_squared_error

from julearn import run_cross_validation
from julearn.utils import configure_logging
from julearn.transformers import register_transformer

start_time = time.time()

def read_data(data_file, demo_file):
    data_df = pickle.load(open(data_file, 'rb')) # read the data
    demo = pd.read_csv(demo_file, ',')     # read demographics file
    data_df = pd.concat([demo[['site', 'subject', 'age', 'gender']], data_df], axis=1) # merge them

    print('Data columns:', data_df.columns)
    print('Data Index:', data_df.index)

    X = [col for col in data_df if col.startswith('f_')]
    y = 'age'
    data_df['age'] = data_df['age'].round().astype(int)  # round off age and convert to integer
    data_df = data_df[data_df['age'].between(18, 90)].reset_index(drop=True)
    data_df.sort_values(by='age', inplace=True, ignore_index=True)  # sort by age
    duplicated_subs_1 = data_df[data_df.duplicated(['subject'], keep='first')] # check for duplicates (multiple sessions for one subject)
    data_df = data_df.drop(duplicated_subs_1.index).reset_index(drop=True)  # remove duplicated subjects
    return data_df, X, y


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo_path", type=str, help="Demographic path")
    parser.add_argument("--data_path", type=str, help="Data path")
    parser.add_argument("--output_filenm", type=str, help="Output file name")
    parser.add_argument("--models", type=str, nargs='?', const=1, default="ridge",
                       help="models to use (comma seperated no space): ridge,rf,rvr_linear")
    parser.add_argument("--pca_status", type=int, default=0,
                       help="0: no pca, 1: yes pca")

    # example arguments
    # demo_file = '../data/ixi/ixi_subject_list_cat12.8.csv'
    # data = '../data/ixi/ixi_173'
    # output_filenm = '../ixi/ixi_173'
    # output_filenm = output_filenm.split('/')
    # output_dir = Path('../results/', output_filenm[0])
    # model_required = ['rvr_lin']
    # output_dir.mkdir(exist_ok=True, parents=True)

    configure_logging(level='INFO')

    # Parse the arguments
    args = parser.parse_args()
    demo_file = args.demo_path
    data = args.data_path
    output_filenm = args.output_filenm
    model_required = [x.strip() for x in args.models.split(',')]  # converts string into list
    pca_status = bool(args.pca_status)

    output_filenm = output_filenm.split('/')
    output_dir = Path('../results/',  output_filenm[0])
    output_dir.mkdir(exist_ok=True, parents=True)

    # initialize random seed and create test indices
    rand_seed = 200
    n_repeats = 5 # for inner CV
    num_splits = 5  # how many train and test splits (both for other and inner)


    print('\nDemographics file: ', demo_file)
    print ('Data file: ', data)
    print ('Ouput path : ', output_dir)
    print ('Model : ', model_required)
    print ('PCA status : ', pca_status)
    print ('Random seed : ', rand_seed)
    print ('Num of splits for kfolds : ', num_splits, '\n')

    # read the data, demo and define X and y
    data_df, X, y = read_data(data_file=data, demo_file=demo_file)

    # Create stratified splits for outer CV
    num_bins = math.floor(len(data_df)/num_splits) # num of bins to be created = num of labels created
    test_indices = stratified_splits(bins_on=data_df.index, num_bins=num_bins, data=data_df, num_splits=num_splits,
                                     shuffle=False, random_state=None)  # creates dictionary of test indices
    all_idx = np.array(range(0, len(data_df)))

    # initialize dictionaries to save scores, models and results
    scores_cv = {k: {} for k in test_indices.keys()}
    models = {k: {} for k in test_indices.keys()}
    results = {k: {} for k in test_indices.keys()}

    # register VarianceThreshold as a transformer
    register_transformer('variancethreshold', VarianceThreshold, returned_features='unknown', apply_to='all_features')
    var_threshold = 1e-5

    # Define all models
    rvr_linear = RVR()
    rvr_poly = RVR()
    kernel_ridge = KernelRidge()
    lasso = ElasticNet(alpha=1, standardize=False)
    elasticnet = ElasticNet(alpha=0.5, standardize=False)
    ridge = ElasticNet(alpha=0, standardize=False)
    xgb = XGBoostAdapted(early_stopping_rounds=10, eval_metric='mae', eval_set_percent=0.2)
    pca = PCA(n_components=None)  # max as many components as sample size

    model_list = [ridge, 'rf', rvr_linear, kernel_ridge, 'gauss', lasso, elasticnet, rvr_poly, xgb]
    model_names = ['ridge', 'rf', 'rvr_lin', 'kernel_ridge', 'gauss', 'lasso', 'elasticnet', 'rvr_poly', 'xgb']

    model_para_list = [{'variancethreshold__threshold': var_threshold, 'elasticnet__random_state': rand_seed},

                       {'variancethreshold__threshold': var_threshold, 'rf__n_estimators': 500, 'rf__criterion': 'mse',
                        'rf__max_features': 0.33, 'rf__min_samples_leaf': 5,
                        'rf__random_state': rand_seed},

                       {'variancethreshold__threshold': var_threshold, 'rvr__kernel': 'linear',
                        'rvr__random_state': rand_seed},

                       {'variancethreshold__threshold': var_threshold,
                        'kernelridge__alpha': [0.0, 0.001, 0.01, 0.1, 0.5, 1.0, 10.0, 100.0, 1000.0],
                        'kernelridge__kernel': 'polynomial', 'kernelridge__degree': [1, 2], 'cv': 5},

                       {'variancethreshold__threshold': var_threshold,
                        'gauss__kernel': gp.kernels.RBF(10.0, (1e-7, 10e7)), 'gauss__n_restarts_optimizer': 100,
                        'gauss__normalize_y': True, 'gauss__random_state': rand_seed},

                       {'variancethreshold__threshold': var_threshold, 'elasticnet__random_state': rand_seed},

                       {'variancethreshold__threshold': var_threshold, 'elasticnet__random_state': rand_seed},

                       {'variancethreshold__threshold': var_threshold, 'rvr__kernel': 'poly', 'rvr__degree': 1,
                        'rvr__random_state': rand_seed},

                       {'variancethreshold__threshold': var_threshold, 'xgboostadapted__n_jobs': 1,
                        'xgboostadapted__max_depth': [6, 8, 10, 12], 'xgboostadapted__n_estimators': 100,
                        'xgboostadapted__reg_alpha': [0.001, 0.01, 0.05, 0.1, 0.2],
                        'xgboostadapted__random_seed': rand_seed, 'cv': 5}]  # 'search_params':{'n_jobs': 5}

    # for each outer CV, run 5X5 fold CV
    iter = 0
    for repeat_key in test_indices.keys():
        print('\n \n--Repeat', repeat_key)
        test_idx = test_indices[repeat_key]  # get test indices
        train_idx = np.delete(all_idx, test_idx)  # get train indices
        train_df, test_df = data_df.loc[train_idx,:], data_df.loc[test_idx,:]  # get test and train dataframes
        train_df, test_df = train_df.reset_index(drop=True), test_df.reset_index(drop=True)
        print('train size:', train_df.shape, 'test size:', test_df.shape)
        qc = pd.cut(train_df[y].tolist(), bins=5)  # create bins for only train set using age, use this for stratification
        # print('age_bins', qc.categories, 'age_codes', qc.codes)

        # Get the model, its parameters, pca status and train
        for ind in range(0, len(model_required)):
            print('model required:', model_required[ind])

            i = model_names.index(model_required[ind])
            assert model_required[ind] == model_names[i]  # sanity check
            print('model picked from the list', model_names[i], model_list[i], '\n')

            if pca_status:
                preprocess_X = ['variancethreshold', 'zscore', pca]
            else:
                preprocess_X = ['variancethreshold', 'zscore']
            print('Preprocessing includes:', preprocess_X)

            cv = RepeatedStratifiedKFold(n_splits=num_splits, n_repeats=n_repeats, random_state=rand_seed).split(train_df, qc.codes)

            scores, model = run_cross_validation(X=X, y=y, data=train_df, preprocess_X=preprocess_X,
                                                 problem_type='regression', model=model_list[i], cv=cv,
                                         return_estimator='final', model_params=model_para_list[i], seed=rand_seed,
                                                 scoring=
                                         ['neg_mean_absolute_error', 'neg_mean_squared_error','r2'])

            scores_cv[repeat_key][model_names[i]] = scores

            if model_names[i] == 'kernel_ridge' or model_names[i] == 'xgb':
                models[repeat_key][model_names[i]] = model.best_estimator_
                print('best model', model.best_estimator_)
                print('best para', model.best_params_)
            else:
                models[repeat_key][model_names[i]] = model
                print('best model', model)

            # Predict on test split
            y_true = test_df[y]
            y_pred = model.predict(test_df[X]).ravel()
            y_delta = y_true - y_pred
            print(y_true.shape, y_pred.shape)
            mae = round(mean_absolute_error(y_true, y_pred), 3)
            mse = round(mean_squared_error(y_true, y_pred), 3)
            corr = round(np.corrcoef(y_pred, y_true)[1, 0], 3)
            print('MAE:', mae, 'MSE:', mse, 'CoRR', corr)
            results[repeat_key][model_names[i]] = {'predictions': y_pred, 'true': y_true, 'test_idx': test_idx,
                                                   'delta': y_delta, 'mae': mae, 'mse': mse, 'corr': corr}


            print('Output file name')
            print(output_dir / f'{output_filenm[1]}_{model_names[i]}.results')

            pickle.dump(results, open(output_dir / f'{output_filenm[1]}_{model_names[i]}.results', "wb"))
            pickle.dump(scores_cv, open(output_dir / f'{output_filenm[1]}_{model_names[i]}.scores', "wb"))
            pickle.dump(models, open(output_dir / f'{output_filenm[1]}_{model_names[i]}.models', "wb"))


        iter = iter + 1
    print('ALL DONE')

    print("--- %s seconds ---" % (time.time() - start_time))
    print("--- %s hours ---" % ((time.time() - start_time)/3600))













