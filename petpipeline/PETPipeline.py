import os
import glob

import nibabel as nib

# Input 
import bids
from bids import BIDSLayout, BIDSValidator
bids.config.set_option('extension_initial_dot', True) #suppress bids warning

from nipype.interfaces.io import SelectFiles

# Nipype 
import nibabel as nib
from nipype import Node, Function
from nipype.pipeline import Node, MapNode, Workflow

# FSL for Motion Correction
from nipype.interfaces import fsl

# IdentityInterface for mappings
from nipype.interfaces.utility import IdentityInterface

# DataSink for storing outputs
from nipype.interfaces.io import DataSink

# Free Surfer for ReconAll
from nipype.interfaces.freesurfer import ReconAll

# PET Surfer for Delineation of Volumes of Interest, Partial Volume Correction, Kinetic Modelling
from nipype.interfaces.freesurfer import petsurfer

# MRICoreg for Coregistration
from nipype.interfaces.freesurfer import MRICoreg

# Helper function for computing time weighted averge
from utils import compute_weighted_average

from config import Config

class PETPipeline:

    def __init__(self, config:Config):
        self.preprocessing_workflow = None
        self.config = config

    def PETWorkflow(self):

        """
        Create a workflow for PET preprocessing. 
        """

        # inititalize workflow
        self.preprocessing_workflow = Workflow(name='preprocessing')

        self.preprocessing_workflow.base_dir = os.path.join(self.config.experiment_dir, self.config.working_dir)

        # data path
        data_path = os.path.join(self.config.experiment_dir,self.config.data_dir)
        
        # create freesurfer dir
        freesurfer_dir = os.path.join(self.config.experiment_dir, 'freesurfer')
        os.system('mkdir -p %s'%freesurfer_dir)

        # Initialize nodes in workflow

        # 1. Motion Correction
        motion_correction = Node(fsl.MCFLIRT(), name="motion_correction")


        # time weighted average
        time_weighted_average = Node(Function(
                                        input_names=["in_file", "json_file"], 
                                        output_names=["out_file"], 
                                        function=compute_weighted_average),
                                        name="time_weighted_average")
                                    
        
        # 2. Co-Registration
        coregistration = Node(MRICoreg(
                                subjects_dir=freesurfer_dir),
                                name="mricoreg")

        # 3.a. Delineation of Volumes of Interest: Run Reconall for all subjects
        reconall = Node(ReconAll(
                            directive='all', 
                            subjects_dir=freesurfer_dir),
                            name="reconall")

        # 3.b. Delineation of Volumes of Interest: Pet Surfer GTMSeg
        gtmseg = Node(petsurfer.GTMSeg(
                        subjects_dir=freesurfer_dir), 
                        name="gtmseg")
  

        mapsubjects = Node(Function(
                            input_names=['session_id','subject_id'], 
                            output_names=['subject_id'], 
                            function=self.map_subjects), name="mapsubjects")

        # 4. Partial Volume Correction 
        partial_volume_correction = Node(petsurfer.GTMPVC(
                                            subjects_dir=freesurfer_dir), name="gtmpvc")
        
        # 5. Kinetic Modelling using MRTM
        kinetic_modelling = Node(petsurfer.MRTM(),name="kinetic_modelling")


        # Streamline Input Output 
        print(data_path)
        layout = BIDSLayout(data_path)
        infosource = Node(IdentityInterface(
                            fields=['subject_id','session_id']),
                            name="infosource")
        infosource.iterables = [('subject_id', layout.get_subjects()), ('session_id', layout.get_sessions())]


        templates = {'anat': 'sub-{subject_id}/ses-{session_id}/anat/*_T1w.nii', 
                    'pet': 'sub-{subject_id}/ses-{session_id}/pet/*_pet.nii.gz', 
                    'json': 'sub-{subject_id}/ses-{session_id}/pet/*_pet.json'}
           
        selectfiles = Node(SelectFiles(templates, base_directory=os.path.join(self.config.experiment_dir,self.config.data_dir)), name="select_files")

        
        datasink = Node(DataSink(base_directory=self.config.experiment_dir, container= self.config.output_dir), name="datasink")
        
        self.preprocessing_workflow.connect([
                                                (infosource, selectfiles, [('subject_id', 'subject_id'),('session_id', 'session_id')]), 
                                                (infosource, mapsubjects, [('subject_id', 'subject_id'),('session_id', 'session_id')]),
                                                (selectfiles, motion_correction, [('pet', 'in_file')]), 
                                                (motion_correction, time_weighted_average, [('out_file','in_file')]),
                                                (selectfiles, time_weighted_average, [('json', 'json_file')]),
                                                (selectfiles, reconall, [('anat','T1_files')]),
                                                (mapsubjects, reconall, [('subject_id','subject_id')]),
                                                (reconall, gtmseg, [('subject_id','subject_id')]),
                                                (reconall, coregistration, [('subject_id','subject_id')]), 
                                                (time_weighted_average, coregistration, [('out_file','source_file')]),
                                                (selectfiles, coregistration, [('anat','reference_file')]),
                                                (motion_correction, partial_volume_correction, [('out_file','in_file')]),
                                                (gtmseg, partial_volume_correction, [('out_file','segmentation')]),
                                                (coregistration, partial_volume_correction, [('out_lta_file','reg_file')])
                                            ])

    def map_subjects(session_id, subject_id):
        """
            Map session ids and subject ids for for recon all 

            Parameters
            ----------
            session_id : str 
                session identifier
            subject_id : str 
                unique subject identifier 

            Returns
            -------
            session_id_subject_id: str
                unique identifier for each session and subject combined
                for storing freesurfer output
        """
        return (session_id + "_" + subject_id)
    
    def run(self):
        self.preprocessing_workflow.write_graph(graph2use="flat")
        self.preprocessing_workflow.run()