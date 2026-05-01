from app.ml.run_similarity import _to_array, compute_run_vector, cosine_similarity, RunSimilarityIndex
import numpy as np

def test_to_array_and_centroid():
    rows = [{"0":1.0,"1":2.0},{"0":3.0,"1":4.0}]
    arr = _to_array(rows)
    assert arr.shape == (2,2)
    vec = compute_run_vector(rows)
    assert vec.tolist() == [2.0, 3.0]

def test_cosine_and_index():
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert abs(cosine_similarity(a,b)) < 1e-6
    idx = RunSimilarityIndex({"a": a, "b": b, "c": np.array([1.0,1.0])})
    sims = idx.most_similar("a", k=2)
    assert sims[0][0] == "c"
