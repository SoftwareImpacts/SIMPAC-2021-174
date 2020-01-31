import copy
import numpy as np
from matplotlib import pyplot as plt

from sklearn.datasets import make_classification
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.dummy import DummyClassifier

from cardinAL.alipy import AlipyWrapper
#from cardinAL.modal import ModalWrapper
from modAL.density import information_density
# from cardinAL.libact import LibactWrapper
from cardinAL.random import RandomSampler
from cardinAL.plotting import plot_confidence_interval

from alipy.query_strategy.query_labels import QueryInstanceGraphDensity


class ModalDensity():

    def __init__(self, n_samples, metric='euclidean'):
        self.n_samples = n_samples
        self.metric = metric

    def fit(self, X, y):
        return self
    
    def predict(self, X):
        selected = np.zeros(X.shape[0], dtype=bool)
        density = information_density(X, self.metric)
        selected[np.argsort(density)[-self.n_samples:]] = True
        return selected


results = dict()

model = SVC(gamma='scale')

n_samples = 1000
n_iter = 20
batch_size = n_samples // n_iter // 2

alipy = AlipyWrapper(model, QueryInstanceGraphDensity, batch_size, train_idx=True)

modal_euclidean = ModalDensity(batch_size)
modal_cosine = ModalDensity(batch_size, metric='cosine')

rand = RandomSampler(batch_size)



# libact = LibactWrapper(model_class, )

results = dict()
for name, method in [
        ('alipy', alipy),
        ('modal-euclidean', modal_euclidean),
        ('modal-cosine', modal_cosine),
        ('random', rand)
    ]:
    folds = []
    for i in range(10):
        X, y = make_classification(n_samples=n_samples + 2, n_features=5, n_informative=5, n_redundant=0,
                           n_repeated=0, n_classes=2, n_clusters_per_class=10, weights=None, flip_y=0.01, class_sep=10.0,
                           hypercube=True, shift=0.0, scale=1.0, shuffle=True, random_state=i)
        
        split_index = n_samples // 2 + 2
        
        X_train = X[:split_index]
        y_train = y[:split_index]
        X_test = X[split_index:]
        y_test = y[split_index:]
        
        selected = np.zeros(X_train.shape[0], dtype=bool)
        # We randomly selected one sample of each class to avoid cases where the training set has only one class
        selected[np.where(y_train == 0)[0][0]] = True
        selected[np.where(y_train == 1)[0][0]] = True
        scores = []
        for j in range(n_iter):
            method.fit(X_train[selected], y_train[selected])
            new_selected = method.predict(X_train[~selected])
            selected[~selected] = new_selected
            score = model.fit(X_train[selected], y_train[selected]).score(X_test, y_test)
            scores.append(score)
        folds.append(scores)
    folds = np.asarray(folds)
    results[name] = folds

    plot_confidence_interval(np.arange(n_iter), folds, label=name)

plt.legend()
plt.show()