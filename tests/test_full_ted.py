import unittest

import numpy as np

from orca_ped_analyzer import compute_energy_distribution, full_ted_matrix_for_mode


class FullTEDTests(unittest.TestCase):
    def setUp(self):
        self.masses=np.array([1.0,2.0])
        self.B=np.array([[1.0,0,0,0,0,0],[0,0,0,1.0,0,0]],float)
        self.F=np.array([[4.0,0.6],[0.6,1.5]],float)
        self.D=np.array([[1.0,0.4],[0.5,1.2]],float)

    def test_full_ted_includes_coupling_and_normalizes(self):
        _,meta=compute_energy_distribution(self.B,self.F,self.D,self.masses,"ted")
        p,k,t=full_ted_matrix_for_mode(self.F,meta["G_inverse"],meta["D_normalized"][:,0],meta["mode_lambda"][0])
        self.assertAlmostEqual(float(p.sum()),1.0,places=10)
        self.assertAlmostEqual(float(k.sum()),1.0,places=10)
        self.assertAlmostEqual(float(t.sum()),1.0,places=10)
        np.testing.assert_allclose(t,t.T,rtol=1e-13,atol=1e-13)
        self.assertNotEqual(float(t[0,1]),0.0)
        np.testing.assert_allclose(t,0.5*(p+k),rtol=1e-13,atol=1e-13)

    def test_full_ted_is_invariant_to_original_mode_scaling(self):
        _,m1=compute_energy_distribution(self.B,self.F,self.D,self.masses,"ted")
        scaled=self.D*np.array([7.1,0.21])[None,:]
        _,m2=compute_energy_distribution(self.B,self.F,scaled,self.masses,"ted")
        for col in range(self.D.shape[1]):
            a=full_ted_matrix_for_mode(self.F,m1["G_inverse"],m1["D_normalized"][:,col],m1["mode_lambda"][col])[2]
            b=full_ted_matrix_for_mode(self.F,m2["G_inverse"],m2["D_normalized"][:,col],m2["mode_lambda"][col])[2]
            np.testing.assert_allclose(a,b,rtol=1e-12,atol=1e-12)


if __name__ == "__main__":
    unittest.main()
