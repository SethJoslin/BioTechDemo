import torch
from torch import nn
import torch.nn.functional as F

class ContrastiveEncoder(nn.Module):
    def __init__(self, input_dim, hidden=256, emb_dim=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, emb_dim)
        )

    def forward(self, x):
        return self.net(x)

    def contrastive_loss(self, z, temperature=0.1):
        z = F.normalize(z, dim=1)
        sim = torch.matmul(z, z.T) / temperature
        labels = torch.arange(z.size(0)).to(z.device)
        loss = F.cross_entropy(sim, labels)
        return loss