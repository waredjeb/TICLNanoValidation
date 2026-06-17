"""Sim-Reco matching utilities."""

import ROOT
from typing import Tuple


class Matcher:
    """Handles Sim-to-Reco and Reco-to-Sim matching."""

    def __init__(self, config):
        """
        Initialize matcher.

        Args:
            config: ValidationConfig object
        """
        self.config = config

    def check_sim_collection_exists(self, rdf: ROOT.RDataFrame, sim_collection: str, reco_collection: str) -> bool:
        """
        Check if sim-to-reco association branches exist.

        Args:
            rdf: RDataFrame to check
            sim_collection: Sim collection name
            reco_collection: Reco collection name

        Returns:
            True if association branches exist
        """
        n_objects, n_links, _, _, _ = self.get_sim2reco_branches(sim_collection, reco_collection)
        columns = set(rdf.GetColumnNames())
        return n_objects in columns and n_links in columns

    def check_reco2sim_exists(self, rdf: ROOT.RDataFrame, reco_collection: str, sim_collection: str) -> bool:
        """
        Check if reco-to-sim association branches exist.

        Args:
            rdf: RDataFrame to check
            reco_collection: Reco collection name
            sim_collection: Sim collection name

        Returns:
            True if association branches exist
        """
        n_objects, n_links, _, _, _ = self.get_reco2sim_branches(reco_collection, sim_collection)
        columns = set(rdf.GetColumnNames())
        return n_objects in columns and n_links in columns

    def get_sim2reco_branches(
        self,
        sim_collection: str,
        reco_collection: str
    ) -> Tuple[str, str, str, str]:
        """
        Get branch names for Sim2Reco association.

        Args:
            sim_collection: Sim collection name (SimCP or SimSC)
            reco_collection: Reco collection name

        Returns:
            Tuple of (n_objects_branch, n_links_branch, index_branch, score_branch, shared_energy_branch)
        """
        # Branch naming pattern: SimCP2ticlTrackstersCLUE3DHighByHits
        assoc_name = f"{sim_collection}2{reco_collection}ByHits"

        n_objects = f"n{assoc_name}"
        n_links = f"{assoc_name}_n{assoc_name}Links"
        index_branch = f"{assoc_name}Links_index"
        score_branch = f"{assoc_name}Links_score"
        shared_energy_branch = f"{assoc_name}Links_sharedEnergy"

        return n_objects, n_links, index_branch, score_branch, shared_energy_branch

    def get_reco2sim_branches(
        self,
        reco_collection: str,
        sim_collection: str
    ) -> Tuple[str, str, str, str, str]:
        """
        Get branch names for Reco2Sim association.

        Args:
            reco_collection: Reco collection name
            sim_collection: Sim collection name (SimCP or SimSC)

        Returns:
            Tuple of (n_objects_branch, n_links_branch, index_branch, score_branch, shared_energy_branch)
        """
        # Branch naming pattern: Reco{reco_collection}2{sim_collection}ByHits
        assoc_name = f"Reco{reco_collection}2{sim_collection}ByHits"

        n_objects = f"n{assoc_name}"
        n_links = f"{assoc_name}_n{assoc_name}Links"
        index_branch = f"{assoc_name}Links_index"
        score_branch = f"{assoc_name}Links_score"
        shared_energy_branch = f"{assoc_name}Links_sharedEnergy"

        return n_objects, n_links, index_branch, score_branch, shared_energy_branch

    def define_sim2reco_matches(
        self,
        rdf: ROOT.RDataFrame,
        sim_collection: str,
        reco_collection: str,
    ) -> ROOT.RDataFrame:
        """
        Define columns for Sim2Reco matching.

        Adds columns:
        - {sim_collection}_matched_to_{reco_collection}: index of best matched reco object (-1 if none)
        - {sim_collection}_match_quality: quality metric (shared energy fraction or score)
        - {sim_collection}_is_matched: boolean indicating if matched

        Args:
            rdf: Input RDataFrame
            sim_collection: Sim collection name
            reco_collection: Reco collection name

        Returns:
            RDataFrame with matching columns defined
        """
        use_score = self.config.matching.method == "score"
        threshold = (
            self.config.matching.sim2reco_score_threshold if use_score
            else self.config.matching.sim2reco_sef_threshold
        )

        # Get branch names
        n_sim, n_links, idx_branch, score_branch, se_branch = \
            self.get_sim2reco_branches(sim_collection, reco_collection)

        # Get raw energy branch for sim collection
        if "SimCP" in sim_collection:
            # For SimCP, we need the ticlSimTrackstersfromCPs collection
            sim_energy_branch = "ticlSimTrackstersfromCPs_raw_energy"
        else:  # SimSC
            sim_energy_branch = "ticlSimTracksters_raw_energy"

        # C++ code to find best match
        match_code = f"""
        std::vector<int> matched_indices;
        std::vector<float> match_qualities;
        std::vector<bool> is_matched;

        int offset = 0;
        for (int i = 0; i < {n_sim}; ++i) {{
            int count = {n_links}[i];

            int best_idx = -1;
            float best_quality = {"9999.0" if use_score else "-1.0"};

            for (int j = 0; j < count; ++j) {{
                int link_idx = offset + j;
                float quality;

                if ({str(use_score).lower()}) {{
                    quality = {score_branch}[link_idx];
                }} else {{
                    // Shared energy fraction = shared_energy / sim_raw_energy
                    float shared_energy = {se_branch}[link_idx];
                    float sim_energy = {sim_energy_branch}[i];
                    quality = (sim_energy > 0) ? (shared_energy / sim_energy) : 0.0;
                }}

                // Best match: lowest score or highest SEF
                bool is_better = {str(use_score).lower()} ?
                    (quality < best_quality) : (quality > best_quality);

                if (is_better) {{
                    best_quality = quality;
                    best_idx = {idx_branch}[link_idx];
                }}
            }}

            // Apply threshold
            bool passes_threshold = {str(use_score).lower()} ?
                (best_quality < {threshold}) : (best_quality > {threshold});

            if (!passes_threshold) {{
                best_idx = -1;
            }}

            matched_indices.push_back(best_idx);
            match_qualities.push_back(best_quality);
            is_matched.push_back(best_idx >= 0);

            offset += count;
        }}

        return std::make_tuple(matched_indices, match_qualities, is_matched);
        """

        # Define the matching columns
        col_prefix = f"{sim_collection}_to_{reco_collection}"
        rdf = (rdf
               .Define(f"{col_prefix}_match_tuple", match_code)
               .Define(f"{col_prefix}_matched", f"std::get<0>({col_prefix}_match_tuple)")
               .Define(f"{col_prefix}_quality", f"std::get<1>({col_prefix}_match_tuple)")
               .Define(f"{col_prefix}_is_matched", f"std::get<2>({col_prefix}_match_tuple)")
               )

        return rdf

    def define_reco2sim_matches(
        self,
        rdf: ROOT.RDataFrame,
        reco_collection: str,
        sim_collection: str,
    ) -> ROOT.RDataFrame:
        """
        Define columns for Reco2Sim matching (fake rate).

        Adds columns:
        - {reco_collection}_matched_to_{sim_collection}: index of best matched sim object (-1 if none)
        - {reco_collection}_match_quality: quality metric
        - {reco_collection}_is_fake: boolean indicating if object is fake (not matched)

        Args:
            rdf: Input RDataFrame
            reco_collection: Reco collection name
            sim_collection: Sim collection name

        Returns:
            RDataFrame with matching columns defined
        """
        use_score = self.config.matching.method == "score"
        threshold = (
            self.config.matching.reco2sim_score_threshold if use_score
            else self.config.matching.reco2sim_sef_threshold
        )

        # Get branch names
        n_reco, n_links, idx_branch, score_branch, se_branch = \
            self.get_reco2sim_branches(reco_collection, sim_collection)

        # Get raw energy branch for reco collection
        reco_energy_branch = f"{reco_collection}_raw_energy"

        # C++ code to find best match (similar to sim2reco but with reco energy for SEF)
        match_code = f"""
        std::vector<int> matched_indices;
        std::vector<float> match_qualities;
        std::vector<bool> is_fake;

        int offset = 0;
        for (int i = 0; i < {n_reco}; ++i) {{
            int count = {n_links}[i];

            int best_idx = -1;
            float best_quality = {"9999.0" if use_score else "-1.0"};

            for (int j = 0; j < count; ++j) {{
                int link_idx = offset + j;
                float quality;

                if ({str(use_score).lower()}) {{
                    quality = {score_branch}[link_idx];
                }} else {{
                    // Shared energy fraction = shared_energy / reco_raw_energy
                    float shared_energy = {se_branch}[link_idx];
                    float reco_energy = {reco_energy_branch}[i];
                    quality = (reco_energy > 0) ? (shared_energy / reco_energy) : 0.0;
                }}

                // Best match: lowest score or highest SEF
                bool is_better = {str(use_score).lower()} ?
                    (quality < best_quality) : (quality > best_quality);

                if (is_better) {{
                    best_quality = quality;
                    best_idx = {idx_branch}[link_idx];
                }}
            }}

            // Apply threshold
            bool passes_threshold = {str(use_score).lower()} ?
                (best_quality < {threshold}) : (best_quality > {threshold});

            if (!passes_threshold) {{
                best_idx = -1;
            }}

            matched_indices.push_back(best_idx);
            match_qualities.push_back(best_quality);
            is_fake.push_back(best_idx < 0);  // Fake if not matched

            offset += count;
        }}

        return std::make_tuple(matched_indices, match_qualities, is_fake);
        """

        # Define the matching columns
        col_prefix = f"{reco_collection}_to_{sim_collection}"
        rdf = (rdf
               .Define(f"{col_prefix}_match_tuple", match_code)
               .Define(f"{col_prefix}_matched", f"std::get<0>({col_prefix}_match_tuple)")
               .Define(f"{col_prefix}_quality", f"std::get<1>({col_prefix}_match_tuple)")
               .Define(f"{col_prefix}_is_fake", f"std::get<2>({col_prefix}_match_tuple)")
               )

        return rdf
