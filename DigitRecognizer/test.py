import pandas as pd
import torch

train = pd.read_csv("data/train.csv")
test = pd.read_csv("data/test.csv")

print(train.shape)  # (42000, 785)

y = train["label"].values
X = train.drop("label", axis=1).values

X = torch.tensor(X, dtype=torch.float32) / 255.0
y = torch.tensor(y, dtype=torch.long)

from torch.utils.data import TensorDataset, DataLoader

dataset = TensorDataset(X, y)

loader = DataLoader(dataset, batch_size=64, shuffle=True)

import torch.nn as nn

model = nn.Linear(784, 10)

criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.SGD(model.parameters(), lr=0.1)

for epoch in range(3):  # 先训练3轮
    total_loss = 0

    for batch_X, batch_y in loader:

        pred = model(batch_X)

        loss = criterion(pred, batch_y)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item()

    print(f"epoch {epoch}, loss = {total_loss:.4f}")

with torch.no_grad():
    pred = model(X)
    pred_label = torch.argmax(pred, dim=1)

    acc = (pred_label == y).float().mean()

print("train accuracy:", acc.item())