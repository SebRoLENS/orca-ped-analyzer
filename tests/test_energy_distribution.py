import unittest

import numpy as np

from orca_ped_analyzer import compute_energy_distribution


class EnergyDistributionTests(unittest.TestCase):
    def setUp(self):
        # Two independent internal coordinates embedded in a 2-atom Cartesian space.
        self.masses = np.array([1.0, 2.0])
        self.B = np.array([
            [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
        ])
        self.F = np.array([
            [4.0, 0.0],
            [0.0, 1.0],
        ])
        self.D = np.array([
            [1.0, 0.5],
            [0.5, 1.0],
        ])

    def test_ped_reproduces_previous_diagonal_formula(self):
        pct, diag = compute_energy_distribution(self.B, self.F, self.D, self.masses, "ped")
        expected_raw = np.diag(self.F)[:, None] * self.D**2
        expected = 100.0 * expected_raw / expected_raw.sum(axis=0)[None, :]
        np.testing.assert_allclose(pct, expected, rtol=1e-13, atol=1e-13)
        self.assertIsNone(diag["G_inverse_diagonal"])
        self.assertIsNone(diag["mode_lambda"])

    def test_ted_is_normalized_nonnegative_and_distinct_from_ped(self):
        ped, _ = compute_energy_distribution(self.B, self.F, self.D, self.masses, "ped")
        ted, diag = compute_energy_distribution(self.B, self.F, self.D, self.masses, "ted")
        np.testing.assert_allclose(ted.sum(axis=0), np.full(ted.shape[1], 100.0), atol=1e-12)
        self.assertTrue(np.all(ted >= 0.0))
        self.assertFalse(np.allclose(ted, ped))
        self.assertTrue(np.all(diag["G_inverse_diagonal"] > 0.0))
        self.assertTrue(np.all(diag["mode_lambda"] > 0.0))

    def test_ted_is_invariant_to_normal_mode_column_scaling(self):
        ted1, _ = compute_energy_distribution(self.B, self.F, self.D, self.masses, "ted")
        scaled = self.D * np.array([3.7, 0.23])[None, :]
        ted2, _ = compute_energy_distribution(self.B, self.F, scaled, self.masses, "ted")
        np.testing.assert_allclose(ted1, ted2, rtol=1e-12, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
