import numpy as np
import torch


# def constants_naming(c_arr):

#     labels = ['A_vwn', 'b_vwn', 'c_vwn', 'x0_vwn', 'A_rpa', 'b_rpa', 'c_rpa', 'x0_rpa', 'params_a_alpha']
#     values = [c_arr[0:2],c_arr[2:4],c_arr[4:6],c_arr[6:8],c_arr[8:11],c_arr[11:14],c_arr[14:17],c_arr[17:20], c_arr[20]]
    
#     return {labels[i]: values[i] for i in range(len(labels))}


#VWN
p_a_zeta_threshold = 1e-15

fpp_vwn = 4/(9*(2**(1/3) - 1))


def Q_vwn(b, c):
    torch.set_printoptions(precision=25)
    x = 4*c - b**2
    if torch.sqrt(x).isnan().any():
        torch.save(x, 'tensor_sqrt.pt')
    
    return torch.sqrt(abs(4*c - b**2))


def f1_vwn(b, c):
    return 2*b/Q_vwn(b, c)


def f2_vwn(b, c, x0):
    return b*x0/(x0**2 + b*x0 + c)


def f3_vwn(b, c, x0):
    return 2*(2*x0 + b)/Q_vwn(b, c)


def fx_vwn(b, c, rs):
    return rs + b*torch.sqrt(rs) + c


def opz_pow_n(z, n):
    if 1 + z <= p_a_zeta_threshold:
        return (p_a_zeta_threshold)^n
    else:
        return (1+z)**n


def f_aux(A, b, c, x0, rs):
    part1 = (f1_vwn(b, c) - f2_vwn(b, c, x0)*f3_vwn(b, c, x0)) * torch.arctan(Q_vwn(b, c)/(2*torch.sqrt(rs) + b))
    f_vwn = (f1_vwn(b, c) - f2_vwn(b, c, x0)*f3_vwn(b, c, x0))
    arc = torch.arctan(Q_vwn(b, c)/(2*torch.sqrt(rs) + b))
    Q = Q_vwn(b, c)
    arc_arg = Q_vwn(b, c)/(2*torch.sqrt(rs) + b)
    torch.set_printoptions(precision=25)
    if part1.isnan().any():
        torch.save(part1, 'tensor_faux_part1.pt')
        torch.save(f_vwn, 'tensor_faux_vwn.pt')
        torch.save(arc, 'tensor_faux_arc.pt')
        torch.save(Q, 'tensor_faux_Q.pt')
        torch.save(arc_arg, 'tensor_faux_arc_arg.pt')
        torch.save(b, 'tensor_faux_b.pt')
        torch.save(c, 'tensor_faux_c.pt')
    print(1)
    return A*(
    + torch.log(rs/fx_vwn(b, c, rs))
    + (f1_vwn(b, c) - f2_vwn(b, c, x0)*f3_vwn(b, c, x0))
    * torch.arctan(Q_vwn(b, c)/(2*torch.sqrt(rs) + b))
    - f2_vwn(b, c, x0)*torch.log((torch.sqrt(rs) - x0)**2/fx_vwn(b, c, rs)))


def DMC(rs, z, c_arr):
    return f_aux(c_arr[:,0:2][:,1], c_arr[:,2:4][:,1], c_arr[:,4:6][:,1], c_arr[:,6:8][:,1], rs) \
    - f_aux(c_arr[:,0:2][:,0], c_arr[:,2:4][:,0], c_arr[:,4:6][:,0], c_arr[:,6:8][:,0], rs)


def DRPA(rs, z, c_arr):
    return f_aux(c_arr[:,8:11][:,1], c_arr[:,11:14][:,1], c_arr[:,14:17][:,1], c_arr[:,17:20][:,1], rs) \
    - f_aux(c_arr[:,8:11][:,0], c_arr[:,11:14][:,0], c_arr[:,14:17][:,0], c_arr[:,17:20][:,0], rs)

#VWN3


def f_zeta(z): # - power threshold
    x = ((1 + z)**(4/3) + (1 - z)**(4/3) - 2)/(2**(4/3) - 2)
    torch.set_printoptions(precision=50)    
    if x.isnan().any():
        torch.save(x, 'tensor_fzeta.pt')
    return ((1 + z)**(4/3) + (1 - z)**(4/3) - 2)/(2**(4/3) - 2)


def f_vwn(rs, z, c_arr):
    return f_aux(c_arr[:,0:2][:,0], c_arr[:,2:4][:,0], c_arr[:,4:6][:,0], c_arr[:,6:8][:,0], rs) \
    + DMC(rs, z, c_arr)/DRPA(rs, z, c_arr)*f_aux(c_arr[:,8:11][:,2], c_arr[:,11:14][:,2], c_arr[:,14:17][:,2], c_arr[:,17:20][:,2], rs) \
    * f_zeta(z)*(1 - z**4)/fpp_vwn + DMC(rs, z, c_arr)*f_zeta(z)*z**4


def rs_z_calc(rho):
    rs = (3/((rho[:,0] + rho[:,1]) * (4 * torch.pi))) ** (1/3)
    z = (rho[:,0] - rho[:,1]) / (rho[:,0] + rho[:,1])
    return rs, z


def f_vwn3(rho, c_arr):
    rs, z = rs_z_calc(rho)
    return f_vwn(rs, z, c_arr)


#SLATER

LDA_X_FACTOR = -3/8*(3/torch.pi)**(1/3)*4**(2/3)
RS_FACTOR = (3/(4*torch.pi))**(1/3)
DIMENSIONS = 3



def f_lda_x(rs, z, c_arr): # - screen_dens threshold
    return c_arr[:,20]*lda_x_spin(rs, z) + c_arr[:,20]*lda_x_spin(rs, -z)


def lda_x_spin(rs, z):
    return LDA_X_FACTOR*(z+1)**(1 + 1/DIMENSIONS)*2**(-1-1/DIMENSIONS)*(RS_FACTOR/rs)


def f_slater(rho, c_arr):
    rs, z = rs_z_calc(rho)
    return f_lda_x(rs, z, c_arr)


def f_svwn3(rho, c_arr):
    '''
    rho.shape = (x, 2)
    c_arr.shape = (x, 21)
    '''
    return f_slater(rho, c_arr) + f_vwn3(rho, c_arr)


if __name__ == '__main__':
    constants_10 = torch.tile(torch.Tensor(
    [0.0310907, 0.01554535, 
                3.72744,   7.06042,
                12.9352,   18.0578,
                -0.10498,  -0.32500,
                0.0310907,  0.01554535,  -1/(6*torch.pi**2),
                13.0720,    20.1231,      1.06835,
                42.7198,   101.578,      11.4813,
                -0.409286,  -0.743294,   -0.228344,
                1]
    ), (10,1))

    rho = torch.tile(torch.Tensor(
    [0.3111, 0.0000]), (10,1))
    
    print(f_svwn3(rho, constants_10))