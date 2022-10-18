import pickle
import pandas as pd
import os.path
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

## cross site (3 sites)
# data_nm = '/camcan_enki_1000brains/camcan_enki_1000brains_'
# data_nm = '/ixi_enki_1000brains/ixi_enki_1000brains_'
data_nm = '/ixi_camcan_enki/ixi_camcan_enki_'
# data_nm = '/ixi_camcan_1000brains/ixi_camcan_1000brains_'

## cross-site (4 sites)
# data_nm = '/ixi_camcan_enki_1000brains/cbpm_4sites_' # with CBPM
# data_nm = '/ixi_camcan_enki_1000brains/4sites_'

results_folder = '/data/project/brainage/brainage_julearn_final/results'

# Filename to save results
cv_file_ext = 'cv_scores.csv'  # 'cv_scores_ModvsUnmod.csv'
test_file_ext = 'test_scores.csv'
combined_file_ext = 'cv_test_scores.csv'
combined_file_ext_selected = 'cv_test_scores_selected.csv'


model_names = ['lin_reg', 'ridge', 'rf', 'rvr_lin', 'kernel_ridge', 'gauss', 'lasso', 'elasticnet', 'rvr_poly'] #'xgb'
model_names_new = ['LiR', 'RR', 'RFR', 'RVRlin', 'KRR', 'GPR', 'LR', 'ENR', 'RVRpoly'] # 'XGB'

data_list = ['173', '473', '873','1273', 'S0_R4', 'S0_R4_pca', 'S4_R4', 'S4_R4_pca', 'S8_R4', 'S8_R4_pca',
                   'S0_R8', 'S0_R8_pca', 'S4_R8', 'S4_R8_pca', 'S8_R8', 'S8_R8_pca']
data_list_new = ['173', '473', '873','1273', 'S0_R4', 'S0_R4 + PCA', 'S4_R4', 'S4_R4 + PCA', 'S8_R4', 'S8_R4 + PCA',
                   'S0_R8', 'S0_R8 + PCA', 'S4_R8', 'S4_R8 + PCA', 'S8_R8', 'S8_R8 + PCA']


cv_filename = results_folder + data_nm + cv_file_ext
print('cv_filename', cv_filename)
test_filename = results_folder + data_nm + test_file_ext
print('test_filename', test_filename)
combined_filename = results_folder + data_nm + combined_file_ext
print('combined_filename', combined_filename)
combined_selected_filename = results_folder + data_nm + combined_file_ext_selected
print('combined_selected_filename', combined_selected_filename)


# get the saved cv scores
df = pd.DataFrame()
df_cv = pd.DataFrame()
for data_item in data_list:
    for model_item in model_names:
        scores_item = results_folder + data_nm + data_item + '.' + model_item + '.scores'  # create the complete path to scores file
        # scores_item = results_folder + data_nm + data_item + '_' + model_item + '.scores'  # create the complete path to scores file
        if os.path.isfile(scores_item):
            res = pickle.load(open(scores_item, 'rb'))
            df = pd.DataFrame()
            mae_all, mse_all, corr_all, corr_delta_all, key_all = list(), list(), list(), list(), list()
            for key, value in res.items():
                mae = round(value['test_neg_mean_absolute_error'].mean() * -1, 3)
                mse = round(value['test_neg_mean_squared_error'].mean() * -1, 3)
                corr = round(value['test_r2'].mean(), 3)
                mae_all.append(mae)
                mse_all.append(mse)
                corr_all.append(corr)
                key_all.append(key)

            df['model'] = key_all
            df['data'] = len(mae_all) * [data_item]
            df['cv_mae'] = mae_all
            df['cv_mse'] = mse_all
            df['cv_corr'] = corr_all
            print(df)
            df_cv = pd.concat([df_cv, df], axis=0)

df_cv = df_cv.reset_index(drop=True)
df_cv['workflow_name'] = df_cv['data'] + ' + ' + df_cv['model']
df_cv['data'] = df_cv['data'].replace(data_list, data_list_new)
df_cv['model'] = df_cv['model'].replace(model_names, model_names_new)

# # get the saved test scores
df = pd.DataFrame()
df_test = pd.DataFrame()
for data_item in data_list:
    for model_item in model_names:
        # scores_item = results_folder + data_nm + data_item + '_cv' + '.' + model_item + '.results'  # create the complete path to scores file
        scores_item = results_folder + data_nm + data_item + '.' + model_item + '.results'  # create the complete path to scores file
        if os.path.isfile(scores_item):
            res = pickle.load(open(scores_item,'rb'))
            df = pd.DataFrame()
            mae_all, mse_all, corr_all, key_all = list(), list(), list(), list()
            for key, value in res.items():
                mae = value['mae']
                mse = value['mse']
                corr = value['corr']
                mae_all.append(mae)
                mse_all.append(mse)
                corr_all.append(corr)
                key_all.append(key)
            df['model'] = key_all
            df['data'] = len(mae_all) * [data_item]
            df['test_mae'] = mae_all
            df['test_mse'] = mse_all
            df['test_corr'] = corr_all
            print(df)
            df_test = pd.concat([df_test, df], axis=0)


df_test = df_test.reset_index(drop=True)
df_test['workflow_name'] = df_test['data'] + ' + ' + df_test['model']
df_test['data'] = df_test['data'].replace(data_list, data_list_new) # update names for data
df_test['model'] = df_test['model'].replace(model_names, model_names_new) # update names for model

df_combined = df_cv.merge(df_test, on=['data', 'model', 'workflow_name'], how="left")
df_combined['workflow_name_updated'] = df_combined['data'] + ' + ' + df_combined['model']
df_combined.reset_index(drop=True, inplace=True)

print(cv_filename)
print(test_filename)
print(combined_filename)



selected_workflows_df = pd.DataFrame([
    '173 + GPR',
    '473 + LR',
    '473 + RVRpoly',
    '1273 + GPR',
    'S4_R4 + RR',
    'S4_R4 + GPR',
    'S4_R4 + PCA + RFR',
    'S4_R4 + PCA + RVRlin',
    'S8_R4 + PCA + RVRlin',
    'S8_R4 + PCA + GPR',
    'S0_R8 + PCA + ENR',
    'S0_R8 + PCA + RVRpoly',
    'S4_R8 + RR',
    'S8_R8 + RR',
    'S8_R8 + KRR',
    'S8_R8 + PCA + ENR',
    'S4_R4 + PCA + GPR',
    'S4_R4 + RVRlin',
    'S4_R4 + PCA + RR',
    'S4_R8 + RVRlin',
    'S8_R4 + KRR',
    'S0_R4 + LR',
    'S8_R4 + PCA + RVRpoly',
    'S0_R8 + RVRpoly',
    'S4_R8 + LR',
    '873 + GPR',
    'S8_R4 + PCA + LR',
    '1273 + RVRpoly',
    '873 + ENR',
    '173 + LR',
    'S0_R8 + PCA + LR',
    '173 + RFR'], columns=['workflow_name_updated'])

# selected_workflows_df = pd.DataFrame([
#     '173 + RFR',
#     '173 + GPR',
#     '173 + LR',
#     '473 + LR',
#     '473 + RVRpoly',
#     '873 + GPR',
#     '873 + ENR',
#     '1273 + GPR',
#     '1273 + RVRpoly',
#     'S0_R4 + LR',
#     'S4_R4 + RR',
#     'S4_R4 + RVRlin',
#     'S4_R4 + GPR',
#     'S4_R4 + PCA + RR',
#     'S4_R4 + PCA + RFR',
#     'S4_R4 + PCA + RVRlin',
#     'S4_R4 + PCA + GPR',
#     'S8_R4 + KRR',
#     'S8_R4 + PCA + RVRlin',
#     'S8_R4 + PCA + GPR',
#     'S8_R4 + PCA + LR',
#     'S8_R4 + PCA + RVRpoly',
#     'S0_R8 + RVRpoly',
#     'S0_R8 + PCA + LR',
#     'S0_R8 + PCA + ENR',
#     'S0_R8 + PCA + RVRpoly',
#     'S4_R8 + RR',
#     'S4_R8 + RVRlin',
#     'S4_R8 + LR',
#     'S8_R8 + RR',
#     'S8_R8 + KRR',
#     'S8_R8 + PCA + ENR'], columns=['workflow_name_updated'])

df_final = df_combined.merge(selected_workflows_df, how='inner', on=['workflow_name_updated'])
print(combined_selected_filename)


df_cv.to_csv(cv_filename, index=False)
df_test.to_csv(test_filename, index=False)
df_combined.to_csv(combined_filename, index=False)
df_final.to_csv(combined_selected_filename, index=False)


# # check model parameeters
# for data_item in data_list:
#     for model_item in model_names:
#         model_item = results_folder + data_nm + data_item + '.' + model_item + '.models'  # get models
#         print('\n','model filename', model_item)
#         if os.path.isfile(model_item):
#             res = pickle.load(open(model_item, 'rb'))
#             # print(res)
#             for key, value in res.items():
#                 print(key)
#                 if key == 'gauss':
#                     model = res['gauss']['gauss']
#                     print(model.kernel_.get_params())
#                 elif key == 'kernel_ridge':
#                     model = res['kernel_ridge']['kernelridge']
#                     print(model)
#                 elif key == 'rvr':
#                     model = res['rvr']['rvr']
#                     print(model)
#                 else:
#                     model = res[key]['elasticnet']
#                     print(model.lambda_best_)









