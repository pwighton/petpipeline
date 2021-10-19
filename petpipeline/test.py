import sys
import argparse

from PETPipeline import PETPipeline
from config import Config

def parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("-e", "--expriment_dir", default="/home/avneet/Desktop/PETWorkflow_",
                        help="The experiment directory")
    parser.add_argument("-o", "--output_dir", default="output_dir/",
                        help="The output directory (relative to the experiment directory)")
    parser.add_argument("-w", "--working_dir", default="working_dir/",
                        help="The working directory (relative to the experiment directory)")
    parser.add_argument("-d", "--data_dir", default="data/",
                        help="The data directory containing the bids dataset (relative to the experiment directory)")                        
    return parser.parse_args()
    
def main(argv):
    args = parse_args(argv)
    print(args.experiment_dir)
    print(args.output_dir)
    print(args.working_dir)
    print(args.data_dir)
    #config = Config(experiment_dir=args.experiment_dir, \
    #                output_dir=args.output_dir, \
    #                working_dir=args.working_dir, \
    #                data_dir=args.data_dir)
    #pipeline = PETPipeline(config)
    #pipeline.PETWorkflow()
    #pipeline.run()
    
if __name__ == "__main__":
    sys.exit(main(sys.argv))
