from openbioops.processing.features import generate_features
import argparse, sys

parser = argparse.ArgumentParser()
parser.add_argument('--counts', required=True)
parser.add_argument('--out', required=True)
args = parser.parse_args()
generate_features(args.counts, args.out)