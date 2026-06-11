# datamind/demo/train.py

# import joblib
# from sklearn.linear_model import LogisticRegression
# import numpy as np
#
# X = np.random.rand(100, 5)
# y = np.random.randint(0, 2, 100)
#
# model = LogisticRegression()
# model.fit(X, y)
#
# joblib.dump(model, "scorecard.pkl")
#
# print(model.n_features_in_)


import joblib
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression

X = pd.DataFrame(
    np.random.rand(100, 5),
    columns=[
        "age",
        "income",
        "gender",
        "province",
        "education",
    ]
)

y = np.random.randint(0, 2, 100)

model = LogisticRegression()
model.fit(X, y)

joblib.dump(model, "scorecard.pkl")

print(model.feature_names_in_)