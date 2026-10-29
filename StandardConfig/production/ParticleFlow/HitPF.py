#!/usr/bin/env python3
# Hit based machine learning particle flow (https://github.com/key4hep/k4PFHitML)
#
# This runs in addition to PandoraPFA and produces the HitPF, HitPFIDs,
# HitPFClusters and HitPFMCTruthLink collections. It is a native Gaudi
# algorithm that consumes EDM4hep collections, so it has to run after the
# LCIO -> EDM4hep conversion of the Marlin processor outputs.
#
# The algorithm takes exactly one collection per calorimeter region. ILD has
# additional ECAL collections (endcap ring and the gap hits), which are merged
# into subset collections first. Using Copy=False keeps the original hits,
# such that the clusters and truth links still refer to the original
# collections and the merged ones do not need to be stored.
#
# The following variables are injected by the SequenceLoader:
# - hitpf_config: dict with the keys
#     model_dir:           directory containing the ONNX models
#     b_field_tesla:       nominal solenoid field [T]
#     ecal_barrel_radius:  inner radius of the ECAL barrel [mm]
#     ecal_barrel_sides:   number of sides of the ECAL barrel polygon
#     ecal_endcap_zmin:    |z| of the ECAL endcap front face [mm]

from Configurables import CollectionMerger, PFHitML
from Gaudi.Configuration import WARNING

HitPFEcalBarrelMerger = CollectionMerger("HitPFEcalBarrelMerger")
HitPFEcalBarrelMerger.InputCollections = [
    "EcalBarrelCollectionRec",
    "EcalBarrelCollectionGapHits",
]
HitPFEcalBarrelMerger.OutputCollection = "HitPFEcalBarrelHits"
HitPFEcalBarrelMerger.Copy = False

HitPFEcalEndcapMerger = CollectionMerger("HitPFEcalEndcapMerger")
HitPFEcalEndcapMerger.InputCollections = [
    "EcalEndcapsCollectionRec",
    "EcalEndcapsCollectionGapHits",
    "EcalEndcapRingCollectionRec",
]
HitPFEcalEndcapMerger.OutputCollection = "HitPFEcalEndcapHits"
HitPFEcalEndcapMerger.Copy = False

HitPF = PFHitML("HitPF")
HitPF.OutputLevel = WARNING
# inputs
HitPF.EcalBarrelHits = ["HitPFEcalBarrelHits"]
HitPF.EcalEndcaplHits = ["HitPFEcalEndcapHits"]  # sic, the property is spelled like this in k4PFHitML
HitPF.HcalBarrelHits = ["HcalBarrelCollectionRec"]
HitPF.HcalEndcapHits = ["HcalEndcapsCollectionRec"]
HitPF.HcalOtherHits = ["HcalEndcapRingCollectionRec"]
HitPF.MUON = ["MUON"]
HitPF.Tracks = ["MarlinTrkTracks"]
HitPF.MCParticles = ["MCParticles"]
HitPF.CalohitMCTruthLink = ["CalohitMCTruthLink"]
HitPF.SiTracksMCTruthLink = ["MarlinTrkTracksMCTruthLink"]
# outputs
HitPF.HitPF = ["HitPF"]
HitPF.HitPFIDs = ["HitPFIDs"]
HitPF.HitPFClusters = ["HitPFClusters"]
HitPF.HitPFMCTruthLink = ["HitPFMCTruthLink"]
HitPF.HitPFUnassociatedTracks = ["HitPFUnassociatedTracks"]
HitPF.writeUnassociatedTracks = False
# models
HitPF.model_path_clustering = f"{hitpf_config['model_dir']}/clustering_paper.onnx"
HitPF.model_path_properties_neutral = f"{hitpf_config['model_dir']}/energy_correction_paper_neutral.onnx"
HitPF.model_path_properties_charged = f"{hitpf_config['model_dir']}/energy_correction_paper_charged_pid.onnx"
# detector dependent parameters: the field is used to get the track momenta
# from the curvature, the ECAL envelope is used for the MC truth matching
HitPF.bFieldTesla = hitpf_config["b_field_tesla"]
HitPF.truth_barrel_radius = hitpf_config["ecal_barrel_radius"]
HitPF.truth_n_barrel_sides = hitpf_config["ecal_barrel_sides"]
HitPF.truth_endcap_z = hitpf_config["ecal_endcap_zmin"]

HitPFSequence = [HitPFEcalBarrelMerger, HitPFEcalEndcapMerger, HitPF]
