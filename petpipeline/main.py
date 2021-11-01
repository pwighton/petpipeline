#!/usr/bin/env python3

import sys
import argparse
import yaml
import os
from PETPipeline import PETPipeline
from config import _EnvConfig, \
                   _MotionCorrectionConfig, \
                   _PartialVolumeCorrectionConfig, \
                   _ReconAllConfig, \
                   _CoregistrationConfig \

from nipype.interfaces.fsl import MCFLIRT

def parse_args(args):
    parser = argparse.ArgumentParser()
    path = os.path.join(os.getcwd(),"petpipeline/config.yaml")
    parser.add_argument("-c", "--config", default=path)
    parser.add_argument("-e", "--experiment_dir", default="/home/avneet/Desktop/PETWorkflow_",
                        help="The experiment directory")
    parser.add_argument("-o", "--output_dir", default="output_dir/",
                        help="The output directory (relative to the experiment directory)")
    parser.add_argument("-w", "--working_dir", default="working_dir/",
                        help="The working directory (relative to the experiment directory)")
    parser.add_argument("-d", "--data_dir", default="data/",
                        help="The data directory containing the bids dataset (relative to the experiment directory)")                        
    return parser.parse_args()

def parse_yaml(file_path):
    
    config = None
    with open(file_path,"r") as stream:
        try:
            config = yaml.load(stream, yaml.FullLoader)
        except yaml.YAMLError as exc:
            print(exc)
    return config
   
def main(argv):
    args = parse_args(argv)

    if args.config:
        config = parse_yaml(args.config)
        env_config = _EnvConfig(**config['environment'])
        motion_correction_config = _MotionCorrectionConfig(**config['motion_correction']) 
        coregistration_config = _CoregistrationConfig(**config['coregistration'])
        reconall_config = _ReconAllConfig(**config['reconall'])
        pvc_config = _PartialVolumeCorrectionConfig(**config['partial_volume_correction'])

    else:
        env_config = _EnvConfig(experiment_dir=args.experiment_dir, \
                        output_dir=args.output_dir, \
                        working_dir=args.working_dir, \
                        data_dir=args.data_dir)
    

    pipeline = PETPipeline(env_config=env_config,
                           motion_correction_config = motion_correction_config, \
                           coregistration_config = coregistration_config, \
                           reconall_config = reconall_config, \
                           pvc_config = pvc_config)
    pipeline.PETWorkflow()
    pipeline.run()
    
if __name__ == "__main__":
    sys.exit(main(sys.argv))
    print(os.getcwd())