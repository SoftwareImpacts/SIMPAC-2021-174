from typing import List
from abc import ABC, abstractmethod
from warnings import warn

import numpy as np

from .typeutils import (RandomStateType, check_random_state,
                        NotEnoughSamplesWarning)


class BaseQuerySampler(ABC):
    """Abstract Base Class for query samplers
    
    A query sampler is an object that takes as input labeled and/or unlabeled
    samples and use knowledge from them to selected the most informative ones.

    Args:
        batch_size: Numbers of samples to select.
    """
    def __init__(self, batch_size: int):
        self.batch_size = batch_size

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray = None):
        """Fit the model on labeled samples.

        Args:
            X: Labeled samples of shape (n_samples, n_features).
            y: Labels of shape (n_samples).
        
        Returns:
            The object itself
        """
        pass

    @abstractmethod
    def select_samples(self, X: np.array) -> np.array:
        """Selects the samples to annotate from unlabeled data.

        Args:
            X: Pool of unlabeled samples of shape (n_samples, n_features).

        Returns:
            Indices of the selected samples of shape (batch_size).
        """
        pass

    def _not_enough_samples(self, X: np.array) -> bool:
        cond = X.shape[0] < self.batch_size
        if cond:
            warn('Requested {} samples but data only has {}.'.format(
                self.batch_size, X.shape[0]), NotEnoughSamplesWarning)
        return cond


class ScoredQuerySampler(BaseQuerySampler):
    """Abstract Base Class handling query samplers relying on a total order.
    Query sampling methods often scores all the samples and then pick samples
    using these scores. This base class handles the selection system, only
    a scoring method is then required.

    Args:
        batch_size: Numbers of samples to select.
        strategy: Describes how to select the samples based on scores. Can be
                  "top", "linear_choice", "squared_choice".
        random_state: Random seeding
    """
    def __init__(self, batch_size: int, strategy: str = 'top',
                 random_state: RandomStateType = None):
        super().__init__(batch_size)
        self.strategy = strategy
        self.random_state = check_random_state(random_state)

    @abstractmethod
    def score_samples(self, X: np.array) -> np.array:
        """Give an informativeness score to unlabeled samples.

        Args:
            X: Samples to evaluate.

        Returns:
            Scores of the samples.
        """
        pass

    def select_samples(self, X: np.array) -> np.array:
        """Selects the samples from unlabeled data using the internal scoring.

        Args:
            X: Pool of unlabeled samples of shape (n_samples, n_features).
            strategy: Strategy to use to select queries. Can be one oftop,
                      linear_choice, or squared_choice.

        Returns:
            Indices of the selected samples of shape (batch_size).
        """
        if self._not_enough_samples(X):
            return np.arange(X.shape[0])

        sample_scores = self.score_samples(X)
        self.sample_scores_ = sample_scores
        if self.strategy == 'top':
            index = np.argsort(sample_scores)[-self.batch_size:]
        elif self.strategy == 'linear_choice':
            index = self.random_state.choice(
                np.arange(X.shape[0]), size=self.batch_size,
                replace=False, p=sample_scores / np.sum(sample_scores))
        elif self.strategy == 'squared_choice':
            sample_scores = sample_scores ** 2
            index = self.random_state.choice(
                np.arange(X.shape[0]), size=self.batch_size,
                replace=False, p=sample_scores / np.sum(sample_scores))
        else:
            raise ValueError('Unknown sample selection strategy {}'
                             .format(self.strategy))
        return index


class ChainQuerySampler(BaseQuerySampler):
    """Allows to chain query sampling methods
    This strategy is usually used to chain a simple query sampler with a
    more complex one. The first query sampler is used to reduce the
    dimensionality.
    """

    def __init__(self, *sampler_list: List[BaseQuerySampler]):
        self.sampler_list = sampler_list

    def fit(self, X: np.array, y: np.array = None) -> 'ChainQuerySampler':
        """Fits the first query sampler

        Args:
            X: Labeled samples of shape [n_samples, n_features].
            y: Labels of shape [n_samples].
        
        Returns:
            The object itself
        """
        self.sampler_list[0].fit(X, y)
        return self
    
    def select_samples(self, X: np.array) -> np.array:
        """Selects the samples by chaining samplers.

        Args:
            X: Pool of unlabeled samples of shape (n_samples, n_features).

        Returns:
            Indices of the selected samples of shape (batch_size).
        """
        selected = self.sampler_list[0].select_samples(X)

        for sampler in self.sampler_list[1:]:
            sampler.fit(X)
            new_selected = sampler.predict(X[selected])
            selected = selected[new_selected]
        
        return selected
