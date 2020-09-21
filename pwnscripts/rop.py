'''An extension of pwnlib.rop.rop.ROP.'''
from pkg_resources import parse_version
from pwnlib import __version__ as PWNLIB_VER
from pwnlib import rop
from pwnlib.rop.call import Call
from pwnlib.util.packing import flat
from pwnlib.shellcraft import registers
from pwnscripts.context import context
class ROP(rop.rop.ROP):
    '''Extended pwnscripts ROP class
    '''
    class Pop():
        '''Internal constructor for ROP.pop
        This class is a wrapper, and should not be called outside of ROP().__init__().
        It is publicly exposed to provide documentation under help() for viewing.
        
        Examples:
        >>> rop = ROP("./binary")
        >>> rop.pop({'rax':0x3b, 'rsi': 0, 'rdx': 0})
        >>> print(rop.dump())
        0x0000:         0x44a309 pop rdx; pop rsi; ret
        0x0008:              0x0
        0x0010:              0x0
        0x0018:         0x41e4af pop rax; ret
        0x0020:             0x3b
        >>> rop = ROP('./binary')
        >>> rop.pop.rdi(1)
        >>> print(rop.dump())
        0x0000:         0x401696 pop rdi; ret
        0x0008:              0x1
        '''
        def __init__(self, rop):
            self.rop = rop
        def __call__(self, regs: dict) -> None:
            '''convinence function to edit a few registers'''
            self.rop._chain += [t[0] for t in self.rop.setRegisters(regs)]
        def __getattr__(self, attr):
            '''Allow for ROP.pop.<register> '''
            if attr not in getattr(registers, context.arch):
                raise AttributeError("module 'ROP.pop' has no attribute %r" % attr)
            # else: Register is being set
            return lambda v: self({attr:v})

    def __init__(self, *a, **kw):
        self.pop = ROP.Pop(self)
        super().__init__(*a, **kw)
    def chain(self, base=None) -> bytes:
        '''Build the ROP chain (and use a `base` if given)

        Returns:
            str containing raw ROP bytes
        '''
        return flat(self.build(base=base))
    def dump(self, base=None) -> str:
        '''Dump the ROP chain in an easy-to-read manner
        Optional `base` argument to change the ROP base'''
        return self.build(base=base).dump()
    def system_call(self, num: int, args: list, ret: bool=False) -> None:
        '''Making system calls without the massive overhead of SIGROP
        >>> context.arch = 'amd64'
        >>> r = ROP('./binary')
        >>> r.system_call(0x3b, ['/bin/sh', 0, 0])
        >>> print(r.dump())
        0x0000:         0x41e4af pop rax; ret
        0x0008:             0x3b
        0x0010:         0x44a309 pop rdx; pop rsi; ret
        0x0018:              0x0 [arg2] rdx = 0
        0x0020:              0x0 [arg1] rsi = 0
        0x0028:         0x401696 pop rdi; ret
        0x0030:             0x40 [arg0] rdi = AppendedArgument(['/bin/sh'], 0x0)
        0x0038:         0x4022b4 syscall
        0x0040:   b'/bin/sh\x00'

        Arguments:
            `num`: the syscall number
            `args`: arguments to the syscall
            `ret`: Specifically use a 'syscall; ret' gadget for syscalls (instead of 'syscall')
                `ret` WILL NOT WORK unless you have the dev verison of pwntools installed.
        
        Returns:
            Nothing. Will raise errors if things go wrong.
        '''
        if context.arch != 'amd64':
            raise NotImplementedError("syscall_call() is only implemented for amd64 right now")
        # get the syscall gadget
        if ret:
            if parse_version(PWNLIB_VER) < parse_version('4.4.0dev0'):
                raise NotImplementedError('"syscall; ret" gadgets are only available on the '
                'latest version of pwntools.')
            syscall = self.find_gadget(['syscall', 'ret'])
        else:
            syscall = self.syscall
        if syscall is None:
            raise AttributeError("ROP unable to find syscall gadget")
        # write the rop chain
        self.pop.rax(num)
        self.raw(Call('syscall', syscall.address, args))