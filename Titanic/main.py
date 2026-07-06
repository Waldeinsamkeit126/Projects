
from pyexpat import features
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.ensemble import GradientBoostingClassifier
from xgboost import XGBClassifier


train = pd.read_csv("data/train.csv")
test = pd.read_csv("data/test.csv")
"""
print(train.groupby("Sex")["Survived"].mean())
print(train.groupby("Pclass")["Survived"].mean())

train["Age"].hist(bins=30)
plt.show()
print(train.groupby(pd.cut(train["Age"], 5))["Survived"].mean())
"""




#train
train["Age"] = train["Age"].fillna(train["Age"].median())
train["Fare"] = train["Fare"].fillna(train["Fare"].median())
train["Embarked"] = train["Embarked"].fillna("S")
train["Sex"] = train["Sex"].map({"male": 0,"female": 1})
#train["Embarked"] = train["Embarked"].map({"S": 0,"C": 1,"Q": 2})#WARNING


#test
test["Age"] = test["Age"].fillna(train["Age"].median())
test["Fare"] = test["Fare"].fillna(train["Fare"].median())
test["Embarked"] = test["Embarked"].fillna("S")
test["Sex"] = test["Sex"].map({"male": 0, "female": 1})
#test["Embarked"] = test["Embarked"].map({"S": 0, "C": 1, "Q": 2})#WARNING



#LogisticRegression
"""
features = ["Pclass", "Sex", "Age", "Fare", "Embarked"]
X = train[features]
y = train["Survived"]
model = LogisticRegression(max_iter=200)
model.fit(X, y)
print("OK")
pred = model.predict(X)
print(accuracy_score(y, pred))
X_train, X_val, y_train, y_val = train_test_split(
    X, y,
    test_size=0.2,
    random_state=42
)

model = LogisticRegression(max_iter=200)
model.fit(X_train, y_train)

pred = model.predict(X_val)

print("验证集accuracy:", accuracy_score(y_val, pred))

X_test = test[features]


pred_test = model.predict(X_test)


submission = pd.DataFrame({
    "PassengerId": test["PassengerId"],
    "Survived": pred_test
})

submission.to_csv("submission.csv", index=False)

print("submission.csv 已生成")
#0.76555
"""


"""
#Title
train["Title"] = train["Name"].str.extract(" ([A-Za-z]+)\.", expand=False)
test["Title"] = test["Name"].str.extract(" ([A-Za-z]+)\.", expand=False)

rare_titles = ["Lady","Countess","Capt","Col","Don","Dr","Major","Rev","Sir","Jonkheer","Dona"]

train["Title"] = train["Title"].replace(rare_titles, "Rare")
test["Title"] = test["Title"].replace(rare_titles, "Rare")

title_map = {"Mr":0, "Miss":1, "Mrs":2, "Master":3, "Rare":4}

train["Title"] = train["Title"].map(title_map)
test["Title"] = test["Title"].map(title_map)

#Family
train["FamilySize"] = train["SibSp"] + train["Parch"] + 1
test["FamilySize"] = test["SibSp"] + test["Parch"] + 1

train["IsAlone"] = (train["FamilySize"] == 1).astype(int)
test["IsAlone"] = (test["FamilySize"] == 1).astype(int)

#Feature
features = [
    "Pclass",
    "Sex",
    "Age",
    "Fare",
    "Embarked",
    "Title",
    "FamilySize",
    "IsAlone"
]
X = train[features]
y = train["Survived"]
X_test = test[features]

#RandomForest
model = RandomForestClassifier(
    n_estimators=300,
    max_depth=5,
    random_state=42
)


#Validate
X_train, X_val, y_train, y_val = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model.fit(X_train, y_train)
val_pred = model.predict(X_val)

print("validation accuracy:", accuracy_score(y_val, val_pred))
model.fit(X, y)
pred_test = model.predict(X_test)
submissionRF = pd.DataFrame({
    "PassengerId": test["PassengerId"],
    "Survived": pred_test
})

submissionRF.to_csv("submissionRF.csv", index=False)

print("submissionRF.csv 已生成")
#0.77751
"""

"""
#Regression
features_A = ["Pclass", "Sex", "Age", "Fare"]
X = train[features_A]
y = train["Survived"]
X_train, X_val, y_train, y_val = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model_A = LogisticRegression(max_iter=300)
model_A.fit(X_train, y_train)

pred_A = model_A.predict(X_val)

print("A Logistic + base features:", accuracy_score(y_val, pred_A))

train["FamilySize"] = train["SibSp"] + train["Parch"] + 1
train["IsAlone"] = (train["FamilySize"] == 1).astype(int)


#Regression+"Family"+"IsAlone"
features_B = ["Pclass", "Sex", "Age", "Fare", "FamilySize", "IsAlone"]
X = train[features_B]
X_train, X_val, y_train, y_val = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model_B = LogisticRegression(max_iter=300)
model_B.fit(X_train, y_train)

pred_B = model_B.predict(X_val)

print("B Logistic + better features:", accuracy_score(y_val, pred_B))


#GradientBoosting
features_C = ["Pclass", "Sex", "Age", "Fare"]
X = train[features_C]
X_train, X_val, y_train, y_val = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model_C = GradientBoostingClassifier(
    n_estimators=200,
    learning_rate=0.05,
    max_depth=3
)

model_C.fit(X_train, y_train)

pred_C = model_C.predict(X_val)

print("C GradientBoosting + base features:", accuracy_score(y_val, pred_C))

##A Logistic + base features: 0.8044692737430168
##B Logistic + better features: 0.7988826815642458
##C GradientBoosting + base features: 0.8156424581005587
"""


"""
#Title
train["Title"] = train["Name"].str.extract(" ([A-Za-z]+)\.", expand=False)
test["Title"] = test["Name"].str.extract(" ([A-Za-z]+)\.", expand=False)

rare_titles = ["Lady","Countess","Capt","Col","Don","Dr","Major","Rev","Sir","Jonkheer","Dona"]

train["Title"] = train["Title"].replace(rare_titles, "Rare")
test["Title"] = test["Title"].replace(rare_titles, "Rare")

title_map = {"Mr":0, "Miss":1, "Mrs":2, "Master":3, "Rare":4}

train["Title"] = train["Title"].map(title_map)
test["Title"] = test["Title"].map(title_map)

#Embarked
train = pd.get_dummies(train, columns=["Embarked"])
test = pd.get_dummies(test, columns=["Embarked"])


test = test.reindex(columns=train.columns, fill_value=0)

features = [
    "Pclass",
    "Sex",
    "Age",
    "Fare",
    "Title",
    "Embarked_C",
    "Embarked_Q",
    "Embarked_S"
]

model = XGBClassifier(
    n_estimators=300,
    learning_rate=0.05,
    max_depth=3,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42
)

X = train[features]
y = train["Survived"]

X_train, X_val, y_train, y_val = train_test_split(
    X, y, test_size=0.2, random_state=42
)

model.fit(X_train, y_train)
pred = model.predict(X_val)

print("CV accuracy:", accuracy_score(y_val, pred))

model.fit(X, y)

X_test = test[features]
pred_test = model.predict(X_test)

submission = pd.DataFrame({
    "PassengerId": pd.read_csv("data/test.csv")["PassengerId"],
    "Survived": pred_test
})

submission.to_csv("submission.csv", index=False)

print("done")
#0.75837
"""