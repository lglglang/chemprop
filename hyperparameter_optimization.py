from argparse import ArgumentParser, Namespace
from typing import Dict, Union

from hyperopt import fmin, hp, tpe
import numpy as np

from chemprop.models import build_model
from chemprop.nn_utils import param_count
from chemprop.parsing import add_train_args, modify_train_args
from chemprop.train import cross_validate
from model_comparison import create_logger, create_train_logger


SPACE = {
    'hidden_size': hp.quniform('hidden_size', low=300, high=2400, q=100),
    'depth': hp.quniform('depth', low=2, high=6, q=1),
    'dropout': hp.quniform('dropout', low=0.0, high=0.4, q=0.05),
    'ffn_num_layers': hp.quniform('ffn_num_layers', low=1, high=3, q=1)
}
INT_KEYS = ['hidden_size', 'depth', 'ffn_num_layers']

TRAIN_LOGGER = create_train_logger()


def grid_search(args: Namespace):
    # Create logger for dataset
    logger = create_logger(name='hyperparameter_optimization', save_path=args.log_path)

    # Run grid search
    results = []

    # Define hyperparameter optimization
    def objective(hyperparams: Dict[str, Union[int, float]]) -> float:
        # Convert hyperparams from float to int when necessary
        for key in INT_KEYS:
            hyperparams[key] = int(hyperparams[key])

        for key, value in hyperparams.items():
            setattr(args, key, value)

        # Record hyperparameters
        logger.info(hyperparams)

        # Cross validate
        mean_score, std_score = cross_validate(args, TRAIN_LOGGER)

        # Record results
        temp_model = build_model(args)
        num_params = param_count(temp_model)
        logger.info(f'num params: {num_params:,}')
        logger.info(f'{mean_score} +/- {std_score} {args.metric}')

        results.append({
            'mean_score': mean_score,
            'std_score': std_score,
            'hyperparams': hyperparams,
            'num_params': num_params
        })

        # Deal with nan
        if np.isnan(mean_score):
            if args.dataset_type == 'classification':
                mean_score = 0
            else:
                raise ValueError('Can\'t handle nan score for non-classification dataset.')

        return (1 if args.minimize_score else -1) * mean_score

    fmin(objective, SPACE, algo=tpe.suggest, max_evals=args.num_iters)

    # Report best result
    results = [result for result in results if not np.isnan(result['mean_score'])]
    best_result = min(results, key=lambda result: (1 if args.minimize_score else -1) * result['mean_score'])
    logger.info('best')
    logger.info(best_result['hyperparams'])
    logger.info(f'num params: {best_result["num_params"]:,}')
    logger.info(f'{best_result["mean_score"]} +/- {best_result["std_score"]} {args.metric}')


if __name__ == '__main__':
    parser = ArgumentParser()
    add_train_args(parser)
    parser.add_argument('--log_path', type=str, required=True,
                        help='Path to .log file where the results of the hyperparameter optimization will be written')
    parser.add_argument('--num_iters', type=int, default=20,
                        help='Number of hyperparameter choices to try')
    args = parser.parse_args()
    modify_train_args(args)

    grid_search(args)
