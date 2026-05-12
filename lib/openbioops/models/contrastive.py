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
    z1 = F.normalize(z1, dim=1)
    z2 = F.normalize(z2, dim=1)
    N = z1.size(0)
    z = torch.cat([z1, z2], dim=0)               # (2N, emb_dim)
    sim = torch.mm(z, z.T) / temperature
    mask = torch.eye(2 * N, dtype=torch.bool, device=z.device)
    sim = sim.masked_fill(mask, float("-inf"))
    labels = torch.cat([torch.arange(N, 2 * N), torch.arange(N)]).to(z.device)
    return F.cross_entropy(sim, labels)

def get_dims_from_checkpoint(state_dict: dict) -> tuple[int, int, int]:
    """Extract (input_dim, hidden_dim, emb_dim) from a state dict."""
    return (
        state_dict["net.0.weight"].shape[1],
        state_dict["net.0.weight"].shape[0],
        state_dict["net.5.weight"].shape[0],
    )