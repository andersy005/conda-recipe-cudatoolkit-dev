#!/usr/bin/env bash

for f in $CONDA_PREFIX/pkgs/cudatoolkit-dev-9.2-0/bin;
do 
    ln -s $f $CONDA_PREFIX/bin/${f};

done


for f in $CONDA_PREFIX/pkgs/cudatoolkit-dev-9.2-0/lib64;
do 
    ln -s $f $CONDA_PREFIX/lib/${f};

done

set CUDA_HOME=$CONDA_PREFIX/pkgs/cudatoolkit-dev-9.2-0/