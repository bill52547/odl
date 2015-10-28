# Copyright 2014, 2015 The ODL development group
#
# This file is part of ODL.
#
# ODL is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ODL is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ODL.  If not, see <http://www.gnu.org/licenses/>.


# Imports for common Python 2/3 codebase
from __future__ import print_function, division, absolute_import

from future import standard_library
standard_library.install_aliases()
from builtins import super

# External module imports
import pytest
import numpy as np

# ODL imports
import odl
import odl.operator.solvers as solvers
from odl.util.testutils import all_almost_equal


class MultiplyOp(odl.Operator):
    """Multiply with a matrix."""

    def __init__(self, matrix, domain=None, range=None):
        dom = odl.Rn(matrix.shape[1]) if domain is None else domain
        ran = odl.Rn(matrix.shape[0]) if range is None else range
        super().__init__(dom, ran, linear=True)
        self.matrix = matrix

    def _apply(self, rhs, out):
        np.dot(self.matrix, rhs.data, out=out.data)

    @property
    def adjoint(self):
        return MultiplyOp(self.matrix.T, self.range, self.domain)


"""Test solutions of the linear equation Ax = b with dense A."""

def test_landweber():
    n = 3

    # Np as validation
    A = np.random.rand(n, n) + np.eye(n) * n
    x = np.random.rand(n)
    # Landweber is slow and needs a decent initial guess
    b = np.dot(A, x)

    # Vector representation
    rn = odl.Rn(n)
    xvec = rn.zero()
    bvec = rn.element(b)

    # Make operator
    norm = np.linalg.norm(A, ord=2)
    Aop = MultiplyOp(A)

    # Solve using landweber
    solvers.landweber(Aop, xvec, bvec, niter=n*10, omega=1/norm**2)
    
    assert all_almost_equal(x, xvec, places=2)
    assert all_almost_equal(Aop(xvec), b, places=2)

def test_conjugate_gradient():
    n = 3

    # Np as validation
    A = np.random.rand(n, n) + np.eye(n) * n
    x = np.random.rand(n)
    b = np.dot(A, x)

    # Vector representation
    rn = odl.Rn(n)
    xvec = rn.zero()
    bvec = rn.element(b)

    # Make operator
    Aop = MultiplyOp(A)

    # Solve using conjugate gradient
    solvers.conjugate_gradient_normal(Aop, xvec, bvec, niter=n)
    
    assert all_almost_equal(x, xvec, places=2)
    assert all_almost_equal(Aop(xvec), b, places=2)

def test_gauss_newton():
    n = 10

    # Np as validation
    A = np.random.rand(n, n) + np.eye(n) * n
    x = np.random.rand(n)
    b = np.dot(A, x)

    # Vector representation
    rn = odl.Rn(n)
    xvec = rn.zero()
    bvec = rn.element(b)

    # Make operator
    Aop = MultiplyOp(A)

    # Solve using conjugate gradient
    solvers.gauss_newton(Aop, xvec, bvec, niter=n*3)
    
    assert all_almost_equal(x, xvec, places=2)
    assert all_almost_equal(Aop(xvec), b, places=2)
    

class ResidualOp(odl.Operator):
    """Calculates op(x) - rhs."""

    def __init__(self, op, rhs):
        super().__init__(op.domain, op.range, linear=False)
        self.op = op
        self.rhs = rhs.copy()

    def _apply(self, x, out):
        self.op(x, out)
        out -= self.rhs

    @property
    def derivative(self, x):
        return self.op.derivative(x)

def test_quasi_newton():
    n = 5

    # Np as validation
    A = np.random.rand(n, n)
    A = np.dot(A.T, A) + np.eye(n) * n

    # Vector representation
    rn = odl.Rn(n)
    xvec = rn.zero()
    rhs = rn.element(np.random.rand(n))

    # Make operator
    Aop = MultiplyOp(A)
    Res = ResidualOp(Aop, rhs)

    x_opt = np.linalg.solve(A, rhs)

    # Solve using quasi newton
    line_search = solvers.BacktrackingLineSearch(lambda x: x.inner(Aop(x)/2.0 - rhs))
    solvers.quasi_newton(Res, xvec, line_search, niter=10)

    assert all_almost_equal(x_opt, xvec, places=2)
    assert Res(xvec).norm() < 10**-1

""" Test on a small QP """

class QPGradientOp(odl.Operator):
    """Gradient operator for a QP, so returns Hx + c."""

    def __init__(self, H, c, domain=None, range=None):
        dom = odl.Rn(H.shape[1]) if domain is None else domain
        ran = odl.Rn(H.shape[0]) if range is None else range
        super().__init__(dom, ran)#, linear=True)
        self.H = H
        self.c = c

    def _call(self, x):
        return self.range.element(np.dot(self.H, x.data) + self.c.ravel())

#    @property
#    def adjoint(self):
#        # TODO: is this correct? 
#        return QPGradientOp(self.H.T, self.c)

def test_steepest_decent():
    """ Solving a quadracit problem min x^T H x + c^T x, where H > 0. Solution
    is given by solving Hx + c = 0, and solving this with np is used as reference. """   
    n = 5
    H = np.random.rand(n, n)
    H = np.dot(H.T, H) + np.eye(n) * n
    c = np.random.rand(n,1)
    
    # Vector representation
    rn = odl.Rn(n)
    xvec = rn.element([3.4])#rn.element([1,1,1,1,1])#rn.zero()

    x_opt = np.linalg.solve(H, -c)
    
    # Create derivative operator operator
    print('H:', H)
    print('c:', c)
    deriv_op = QPGradientOp(H,c)

    # Solve using steepest decent
    line_search = solvers.BacktrackingLineSearch(lambda x: x.inner(deriv_op(x)) )
    solvers.steepest_decent(deriv_op , xvec, line_search, niter=200)
    
    assert all_almost_equal(x_opt, xvec, places=2)
    
if __name__ == '__main__':
    pytest.main(str(__file__.replace('\\','/')) + ' -v')

