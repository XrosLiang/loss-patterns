"""
Exports data from tensorboard logs to csv for our experiments
"""
import os
import argparse
from typing import List, Dict, Tuple

import pandas as pd
from tqdm import tqdm
from firelab.config import Config
from firelab.utils.fs_utils import clean_dir
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator


def main(exp_name:str, output_dir:os.PathLike):
    logs_dir = f'experiments/{exp_name}/logs'
    summaries_dir = f'experiments/{exp_name}/summaries'
    output_exp_dir = os.path.join(output_dir, exp_name)

    hpo_exp_names = sorted([exp for exp in os.listdir(logs_dir)])
    hps = []
    val_acc_diffs = []
    finished_exps = []
    images = []

    for i, hpo_exp_name in tqdm(enumerate(hpo_exp_names), total=len(hpo_exp_names)):
        assert len(get_dir_children(os.path.join(logs_dir, hpo_exp_name))) == 1, \
            f"Multiple logs are stored in {os.path.join(logs_dir, hpo_exp_name)}. That's ambigous."

        # if i > 1: break

        summary_path = os.path.join(summaries_dir, f'{hpo_exp_name}.yml')
        logs_path = get_dir_children(os.path.join(logs_dir, hpo_exp_name))[0]

        if not os.path.exists(summary_path):
            print(f'Skipping {hpo_exp_name} because summary does not exist yet')
            continue

        curr_val_acc_diffs, curr_hp, curr_image_test, curr_image_train = extract_data(summary_path, logs_path)

        if len(curr_val_acc_diffs) != 100:
            print(f'Skipping {hpo_exp_name} because not finished yet (only {len(curr_val_acc_diffs)})')
            continue

        if curr_image_test is None:
            print(f'Skipping {hpo_exp_name} because image does not yet')
            continue

        val_acc_diffs.append(curr_val_acc_diffs)
        hps.append(curr_hp)
        images.append(curr_image_test)
        finished_exps.append(hpo_exp_name)

    # print('val_acc_diffs', val_acc_diffs)
    # print('hps', hps)
    # print('finished_exps', finished_exps)

    val_acc_diffs = pd.DataFrame.from_dict({exp: values for exp, values in zip(finished_exps, val_acc_diffs)})
    hps = pd.DataFrame(data=hps, index=finished_exps)

    clean_dir(output_exp_dir, create=True)
    val_acc_diffs.to_csv(os.path.join(output_exp_dir, 'val_acc_diffs.csv'))
    hps.to_csv(os.path.join(output_exp_dir, 'hps.csv'))

    os.mkdir(os.path.join(output_exp_dir, 'images'))
    for exp_name, image in zip(finished_exps, images):
        with open(os.path.join(output_exp_dir, 'images', f'{exp_name}.png'), 'wb') as f:
            f.write(image)


def extract_data(summary_path:os.PathLike, logs_path:os.PathLike) -> Tuple[List[float], Dict, str]:
    config = Config.load(summary_path).config
    events_acc = EventAccumulator(logs_path)
    events_acc.Reload()

    _, _, val_acc_diffs = zip(*events_acc.Scalars('diff/val/acc'))
    hp = config.hp.to_dict()
    hp['n_conv_layers'] = len(config.hp.conv_model_config.conv_sizes)

    if 'Minimum_test' in events_acc.images.Keys():
        image_test = events_acc.Images('Minimum_test')[0].encoded_image_string
        image_train = events_acc.Images('Minimum_train')[0].encoded_image_string
    else:
        image_test = None
        image_train = None

    return val_acc_diffs, hp, image_test, image_train


def get_dir_children(dir:str) -> List[str]:
    return [os.path.join(dir, f) for f in os.listdir(dir)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Expoert tensorboard experimentcsv')
    parser.add_argument('-e', '--experiment_name', type=str, required=True, metavar='experiment_name',
        help='Experiment name which will be looked up in `experiments` directory (for example, "super-experiment-00017"')
    parser.add_argument('-o', '--output_dir', type=str, default='logs_export', metavar='output_dir',
        help='Path to a directory where the results will be saved')

    args = parser.parse_args()

    main(args.experiment_name, args.output_dir)
