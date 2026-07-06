import pandas as pd
import torch
from torch.utils.data import DataLoader, TensorDataset
import torch.nn as nn
import torch.nn.functional as F

# =========================
# 1. 读取数据
# =========================
train = pd.read_csv("data/train.csv")
test = pd.read_csv("data/test.csv")

y = torch.tensor(train["label"].values, dtype=torch.long)
X = torch.tensor(train.drop("label", axis=1).values, dtype=torch.float32)
X = X.view(-1, 1, 28, 28) / 255.0

X_test = torch.tensor(test.values, dtype=torch.float32)
X_test = X_test.view(-1, 1, 28, 28) / 255.0

# =========================
# 2. DataLoader
# =========================
loader = DataLoader(
    TensorDataset(X, y),
    batch_size=32,
    shuffle=True
)

test_loader = DataLoader(
    X_test,
    batch_size=64,
    shuffle=False
)

# =========================
# 3. CNN模型
# =========================
class CNN(nn.Module):
    def __init__(self):
        super().__init__()

        self.conv1 = nn.Conv2d(1, 32, 3)
        self.conv2 = nn.Conv2d(32, 64, 3)

        self.pool = nn.MaxPool2d(2)

        self.fc = nn.Linear(64 * 12 * 12, 10)

    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))

        x = self.pool(x)

        x = x.view(x.size(0), -1)

        x = self.fc(x)

        return x


model = CNN()

# =========================
# 4. 训练
# =========================
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

for epoch in range(3):
    total_loss = 0

    for batch_X, batch_y in loader:

        pred = model(batch_X)
        loss = criterion(pred, batch_y)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item()

    print("epoch:", epoch, "loss:", total_loss)

# =========================
# 5. 预测 test
# =========================
model.eval()

preds = []

with torch.no_grad():
    for batch in test_loader:
        out = model(batch)
        preds.append(out)

preds = torch.cat(preds)
labels = preds.argmax(dim=1)

# =========================
# 6. 生成 submission.csv
# =========================
submission = pd.DataFrame({
    "ImageId": range(1, len(labels) + 1),
    "Label": labels.numpy()
})

submission.to_csv("submission.csv", index=False)

print("DONE - submission.csv generated")