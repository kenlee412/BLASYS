import regex as re
import sys
import random
import os
import numpy as np
import subprocess

def assess_HD(original_path, approximate_path):
    with open(original_path, 'r') as fo:
        org_line_list = fo.readlines()
    with open(approximate_path, 'r') as fa:
        app_line_list = fa.readlines()
    
    org_size = len(org_line_list)
    app_size = len(app_line_list)

    if org_size != app_size:
        print('ERROR! sizes of input files are not equal! Aborting...')
        return -1

    HD=0
    total=0
    for n in range(org_size):
        l1=org_line_list[n]
        l2=app_line_list[n]
        for k in range(len(l1)):
            total+=1
            if l1[k] != l2[k]:
                HD+=1
    return [total, HD, HD/total]

def synth_design(input_file, output_file, lib_file):
    f=open('abc.script', 'w')
    f.write('bdd;collapse;order;map')
  #  f.write('strash;refactor;rewrite;refactor;rewrite;refactor;rewrite;map')
 #   f.write('espresso;map')
    f.close
    f=open('yosys.script', 'w')
    yosys_command = 'read_verilog ' + input_file + '; ' \
            + 'synth -flatten; opt; opt_clean -purge; techmap; abc -liberty '+lib_file + '; ' \
            + 'stat -liberty '+lib_file + '; ' \
            + 'write_verilog -noattr -noexpr ' + output_file + '.v;\n'
    f.write(yosys_command)
    f.close
    area = 0
    line=subprocess.call("yosys -p \'"+ yosys_command+"\' > "+ output_file+".log", shell=True, stdout=f)
    with open(output_file+".log", 'r') as file_handle:
        for line in file_handle:
            if 'Chip area' in line:
                area = line.split()[-1]
    return float(area)


def gen_truth(fname, modulename):
    with open(fname+'.v') as file:
        f=open(fname+'_tb.v', "w+")
        line = file.readline()
        inp=0
        out=0
        n_inputs=0
        n_outputs=0
        while line:
            line.strip()
            tokens=re.split('[ ,;\n]', line)
            for t in tokens:			
                t.strip()
                if t != "":
                    if inp == 1 and t != 'output':
                        n_inputs+=1
                    if out == 1 and t != 'wire':
                        n_outputs+=1
                    if t == 'input':
                        inp=1
                    elif t == 'output':
                        out=1
                        inp=0
                    elif t == 'wire':
                        out=0
            line=file.readline()
        file.close()
    f.write("module "+modulename+"_tb;\n")
    f.write('reg ['+str(n_inputs-1)+':0] pi;\n')
    f.write('wire ['+str(n_outputs-1)+':0] po;\n')
    f.write(modulename+' dut(')
    with open(fname+'.v') as file:
        line = file.readline()
        inp=0
        out=0
        first=1
        i=0
        while line:
            line.strip()
            tokens=re.split('[ ,;\n]', line)
            for t in tokens:			
                t.strip()
                if t != "":
                    if inp == 1 and t != 'output':
                        if first==0:
                            #f.write(', '+t, end='')
                            f.write(', pi['+str(n_inputs-i-1)+']')
                        else:
                            first=0
                            f.write('pi['+str(n_inputs-i-1)+']')
                        i=i+1
                    if out == 1 and t != 'wire':
                        if first == 0:
                            #f.write(', '+t, end='')
                            f.write(', po['+str(n_outputs-i-1)+']')
                        else:
                            first=0
                            f.write(', po['+str(n_outputs-i-1)+']')
                        i+=1
                    if t == 'input':
                        inp=1
                    elif t == 'output':
                        i=0
                        first=1
                        out=1
                        inp=0
                    elif t == 'wire':
                        f.write(');\n')
                        out=0
            line=file.readline()
        file.close()
    f.write("initial\n")
    f.write("begin\n")
    j=0
    while j < 2**n_inputs:
        f.write('# 1  pi='+str(n_inputs)+'\'b')
        str1=bin(j).replace("0b", "")
        str2="0"*(n_inputs-len(str1))
        n=str2+str1
        f.write(n)
        f.write(';\n')
        f.write("#1 $display(\"%b\", po);\n")
        j+=1
    f.write("end\n")
    f.write("endmodule\n")
    f.close()
    return n_inputs, n_outputs


def v2w(signal,  n):
    s=''
    for i in range(n-1, 0, -1):
        s = s+signal+str(i)+', '
    s=s+signal+'0'
    return s

def create_w(n, k, W, f1):    
    f1.write('module w'+str(k)+'('+v2w('in', n)+', '+ v2w('k', k)+');\n')
    f1.write('input '+v2w('in', n)+';\n')
    f1.write('output '+v2w('k', k)+';\n')

    for i in range(k-1, -1, -1):
        f1.write('assign k'+str(k-i-1)+' = ')
        not_first=0
        constant=1
        for j in range(2 ** n):
            if W[j,i] == 1:
                constant = 0
                if (not_first):
                    f1.write(' | ')
                not_first=1
                str1=bin(j).replace("0b", "")
                str2="0"*(n-len(str1))
                num=str2+str1
                if (num[len(num)-1] == '1'):
                    f1.write('(in0')
                else:
                    f1.write('(~in0')
                for ii in range(2, len(num)+1):
                    if num[len(num)-ii] == '1':
                        f1.write(' & in'+str(ii-1))
                    else:
                        f1.write(' & ~in'+str(ii-1))
                f1.write(')')
        if constant == 1:
            f1.write('0')
        f1.write(';\n')    
    f1.write('endmodule\n\n')

def create_h(m, k, H, f1):
    f1.write('module h'+str(k)+'('+v2w('k', k)+', '+ v2w('out', m)+');\n')
    f1.write('input '+v2w('k', k)+';\n')
    f1.write('output '+v2w('out', m)+';\n')
    # Print The gates...
    for i in range(m-1, -1, -1):
        f1.write('assign out'+str(m-i-1)+' = ')
        not_first=0
        constant=1
        for j in  range(k):
            if H[j,i] == 1:
                constant=0
                if (not_first):
                    f1.write(' | k'+str(k - j -1))
                else:
                    f1.write('k'+str(k - j - 1))
                not_first=1
        if constant == 1:
            f1.write('0')
        f1.write(';\n')
    
    f1.write('endmodule\n')



def create_wh(n, m, k, W, H, fname):
    f1=open(fname+'_approx_k='+str(k)+'.v','w')
    f1.write('module ' +fname+'(' + v2w('in', n)+', '+ v2w('out', m)+');\n')
    f1.write('input '+v2w('in', n)+';\n')
    f1.write('output '+v2w('out', m)+';\n')
    f1.write('wire '+v2w('k', k)+';\n')
    f1.write('w'+str(k)+' DUT1 ('+v2w('in', n)+', '+ v2w('k', k)+');\n')
    f1.write('h'+str(k)+' DUT2 ('+v2w('k', k)+', '+ v2w('out', m)+');\n')
    f1.write('endmodule\n\n')
    create_w(n, k, W, f1)
    create_h(m, k, H, f1)
    f1.close

	