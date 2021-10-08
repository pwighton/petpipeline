from PETPipeline import PETPipeline
from config import Config

if __name__== "__main__":
    experiment_dir = "/home/avneet/Desktop/PETWorkflow_"
    output_dir = 'output_dir/'  
    working_dir = 'working_dir/'
    data_dir = "data/"

    config = Config(experiment_dir=experiment_dir, output_dir=output_dir, working_dir=working_dir, data_dir=data_dir)
    pipeline = PETPipeline(config)
    pipeline.PETWorkflow()
    pipeline.run()
