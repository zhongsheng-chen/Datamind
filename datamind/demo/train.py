# train.py

import joblib
from sklearn.linear_model import LogisticRegression
import numpy as np

X = np.random.rand(100, 5)
y = np.random.randint(0, 2, 100)

model = LogisticRegression()
model.fit(X, y)

joblib.dump(model, "scorecard.pkl")