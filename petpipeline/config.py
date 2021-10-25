import os
from dataclasses import dataclass

@dataclass
class Config:

    """
        A configuration class for the pet pipeline

        Attributes
        ----------
        data_dir : str
            Path to data directory
        experiment_dir: str
            Path to experiments directory
        working_dir : str 
            Path to the working directory
        output_dir : str
            Path to output directory

    """
    
    data_dir: str
    experiment_dir: str
    working_dir: str
    output_dir: str