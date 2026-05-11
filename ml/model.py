import torch
from torch import nn
import torch.nn.functional as F


class ContrastiveEncoder(nn.Module):
    def __init__(self, input_dim: int, hidden: int = 256, emb_dim: int = 64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden),
            nn.BatchNorm1d(hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden),
            nn.ReLU(),
            nn.Linear(hidden, emb_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def nt_xent_loss(z1: torch.Tensor, z2: torch.Tensor, temperature: float = 0.1) -> torch.Tensor:
    """
    NT-Xent (Normalized Temperature-scaled Cross Entropy) loss.
    z1 and z2 are embeddings of two augmented views of the same samples.
    Shape: (N, emb_dim) each.
    """
    z1 = F.normalize(z1, dim=1)
    z2 = F.normalize(z2, dim=1)

    N = z1.size(0)
    z = torch.cat([z1, z2], dim=0)               # (2N, emb_dim)
    sim = torch.mm(z, z.T) / temperature          # (2N, 2N)

    # mask out self-similarity on the diagonal
    mask = torch.eye(2 * N, dtype=torch.bool, device=z.device)
    sim = sim.masked_fill(mask, float("-inf"))

    # positive pairs: (i, i+N) and (i+N, i)
    labels = torch.cat([torch.arange(N, 2 * N), torch.arange(N)]).to(z.device)
    loss = F.cross_entropy(sim, labels)
    return loss
