"""
Generate a test fixture model for integration testing.

This script creates a synthetically-initialized ContrastiveEncoder that matches
the production model's architecture but uses random weights for deterministic,
fast testing. The fixture enables integration tests to validate:
- Model loading and state dict format compatibility
- Inference pipeline shape handling
- Feature dimension matching
- Embedding generation without requiring trained weights

This is NOT a trained model - it's an architectural fixture for testing.

Usage:
    python ml/generate_test_model.py [--input-dim 50] [--hidden-dim 256] [--emb-dim 64]

Or via Make:
    make generate-test-model
"""
import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "lib"))

import torch
from openbioops.models.contrastive import ContrastiveEncoder, get_dims_from_checkpoint


def generate_test_fixture(
    output_path: Path,
    input_dim: int = 50,
    hidden_dim: int = 256,
    emb_dim: int = 64,
    seed: int = 42,
    validate_against: Path | None = None,
) -> None:
    """Generate a test model fixture with specified architecture.

    Args:
        output_path: Path to save the model checkpoint
        input_dim: Input feature dimension
        hidden_dim: Hidden layer dimension
        emb_dim: Embedding output dimension
        seed: Random seed for reproducibility
        validate_against: Optional production checkpoint to validate format against
    """
    # Set seed for reproducibility
    torch.manual_seed(seed)

    # Validate against production checkpoint if provided
    if validate_against and validate_against.exists():
        print(f"Validating architecture against: {validate_against}")
        prod_state = torch.load(validate_against, map_location="cpu")
        prod_input, prod_hidden, prod_emb = get_dims_from_checkpoint(prod_state)

        if (input_dim, hidden_dim, emb_dim) != (prod_input, prod_hidden, prod_emb):
            print(f"  WARNING: Dimension mismatch with production model:")
            print(f"    Production: input={prod_input}, hidden={prod_hidden}, emb={prod_emb}")
            print(f"    Test fixture: input={input_dim}, hidden={hidden_dim}, emb={emb_dim}")
            print(f"  Using production dimensions to maintain compatibility.")
            input_dim, hidden_dim, emb_dim = prod_input, prod_hidden, prod_emb

    # Create model with production architecture
    model = ContrastiveEncoder(
        input_dim=input_dim,
        hidden=hidden_dim,
        emb_dim=emb_dim
    )

    # Initialize weights with Xavier initialization (better than random)
    for module in model.modules():
        if isinstance(module, torch.nn.Linear):
            torch.nn.init.xavier_uniform_(module.weight)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, torch.nn.BatchNorm1d):
            torch.nn.init.ones_(module.weight)
            torch.nn.init.zeros_(module.bias)

    # Save state dict
    output_path.parent.mkdir(parents=True, exist_ok=True)
    state_dict = model.state_dict()
    torch.save(state_dict, output_path)

    # Verify saved checkpoint can be loaded
    loaded_state = torch.load(output_path, map_location="cpu")
    loaded_input, loaded_hidden, loaded_emb = get_dims_from_checkpoint(loaded_state)

    assert loaded_input == input_dim, f"Input dim mismatch: {loaded_input} != {input_dim}"
    assert loaded_hidden == hidden_dim, f"Hidden dim mismatch: {loaded_hidden} != {hidden_dim}"
    assert loaded_emb == emb_dim, f"Emb dim mismatch: {loaded_emb} != {emb_dim}"

    print(f"✓ Test fixture generated: {output_path}")
    print(f"  Architecture: input={input_dim} → hidden={hidden_dim} → emb={emb_dim}")
    print(f"  State dict keys: {list(loaded_state.keys())}")
    print(f"  Total parameters: {sum(p.numel() for p in model.parameters()):,}")


def main():
    parser = argparse.ArgumentParser(description="Generate test model fixture")
    parser.add_argument(
        "--input-dim",
        type=int,
        default=50,
        help="Input feature dimension (default: 50 for PCA features)"
    )
    parser.add_argument(
        "--hidden-dim",
        type=int,
        default=256,
        help="Hidden layer dimension (default: 256)"
    )
    parser.add_argument(
        "--emb-dim",
        type=int,
        default=64,
        help="Embedding dimension (default: 64)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=project_root / "ml" / "model.pt",
        help="Output path for test model"
    )
    parser.add_argument(
        "--validate-against",
        type=Path,
        help="Production checkpoint to validate format against"
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("  Test Model Fixture Generation")
    print("=" * 70)
    print()
    print("This generates a synthetically-initialized model for testing.")
    print("The model has production-equivalent architecture but untrained weights.")
    print()

    generate_test_fixture(
        output_path=args.output,
        input_dim=args.input_dim,
        hidden_dim=args.hidden_dim,
        emb_dim=args.emb_dim,
        seed=args.seed,
        validate_against=args.validate_against,
    )

    print()
    print("=" * 70)
    print("✓ Test fixture ready for integration testing")
    print("=" * 70)


if __name__ == "__main__":
    main()