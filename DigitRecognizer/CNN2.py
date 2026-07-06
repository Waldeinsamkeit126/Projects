import pandas as pd
import torch
from torch.utils.data import DataLoader, TensorDataset
import torch.nn as nn
import torch.nn.functional as F


train = pd.read_csv("data/train.csv")
test = pd.read_csv("data/test.csv")

y = torch.tensor(train["label"].values, dtype=torch.long)
X = torch.tensor(train.drop("label", axis=1).values, dtype=torch.float32)

X = X.view(-1, 1, 28, 28) / 255.0

X_test = torch.tensor(test.values, dtype=torch.float32)
X_test = X_test.view(-1, 1, 28, 28) / 255.0


train_loader = DataLoader(
    TensorDataset(X, y),
    batch_size=64,
    shuffle=True
)

test_loader = DataLoader(
    X_test,
    batch_size=128,
    shuffle=False
)

class CNN(nn.Module):
    def __init__(self):
        super().__init__()

        self.conv1 = nn.Conv2d(1, 32, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(32)

        self.conv2 = nn.Conv2d(32, 64, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(64)

        self.conv3 = nn.Conv2d(64, 128, 3, padding=1)
        self.bn3 = nn.BatchNorm2d(128)

        self.pool = nn.MaxPool2d(2)
        self.dropout = nn.Dropout(0.5)

        self.fc = nn.Linear(6272, 10)
    def forward(self, x):

        x = F.relu(self.bn1(self.conv1(x)))
        x = F.relu(self.bn2(self.conv2(x)))
        x = self.pool(x)

        x = F.relu(self.bn3(self.conv3(x)))
        x = self.pool(x)

        x = x.view(x.size(0), -1)

        x = self.dropout(x)

        x = self.fc(x)

        return x


model = CNN()

criterion = nn.CrossEntropyLoss()

optimizer = torch.optim.AdamW(model.parameters(), lr=0.001)

scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
    optimizer,
    T_max=10
)

for epoch in range(10):

    total_loss = 0

    for batch_X, batch_y in train_loader:

        pred = model(batch_X)
        loss = criterion(pred, batch_y)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        total_loss += loss.item()

    scheduler.step()

    print(f"epoch {epoch}, loss {total_loss:.4f}")


model.eval()

preds = []

with torch.no_grad():
    for batch in test_loader:
        out = model(batch)
        preds.append(out)

preds = torch.cat(preds)
labels = preds.argmax(dim=1)

submission = pd.DataFrame({
    "ImageId": range(1, len(labels) + 1),
    "Label": labels.numpy()
})

submission.to_csv("submission.csv", index=False)

print("DONE")
#0.99228