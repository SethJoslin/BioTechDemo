import argparse
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset
from model import ContrastiveEncoder

class TabularDataset(Dataset):
    def __init__(self, df):
        self.X = df.values.astype('float32')
    def __len__(self): return len(self.X)
    def __getitem__(self, idx): return self.X[idx]

def train(args):
    df = pd.read_parquet(args.input)
    ds = TabularDataset(df)
    dl = DataLoader(ds, batch_size=256, shuffle=True)
    model = ContrastiveEncoder(input_dim=df.shape[1], hidden=256, emb_dim=64)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    for epoch in range(args.epochs):
        for x in dl:
            z = model(x)
            loss = model.contrastive_loss(z)
            opt.zero_grad(); loss.backward(); opt.step()
    torch.save(model.state_dict(), args.out)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--epochs", type=int, default=10)
    args = parser.parse_args()
    train(args)