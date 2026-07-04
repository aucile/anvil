# Request #2: write me a program to give the overall charge of a protein given its pdb id
# Completed with 2 subtask(s)

import io
import sys
import requests
from Bio.PDB import PDBParser

# ---------------------------------------------------------------------------
# pKa values for ionisable side-chains and termini (standard / Lehninger)
# ---------------------------------------------------------------------------
PKA_VALUES = {
    "ARG":  {"pKa": 12.5, "charge_below": +1, "charge_above": 0},
    "LYS":  {"pKa": 10.5, "charge_below": +1, "charge_above": 0},
    "HIS":  {"pKa":  6.0, "charge_below": +1, "charge_above": 0},
    "ASP":  {"pKa":  3.9, "charge_below":  0, "charge_above": -1},
    "GLU":  {"pKa":  4.1, "charge_below":  0, "charge_above": -1},
    "CYS":  {"pKa":  8.3, "charge_below":  0, "charge_above": -1},
    "TYR":  {"pKa": 10.1, "charge_below":  0, "charge_above": -1},
    # N-terminus and C-terminus are handled separately
    "NTERM": {"pKa": 8.0, "charge_below": +1, "charge_above": 0},
    "CTERM": {"pKa": 3.1, "charge_below":  0, "charge_above": -1},
}

IONISABLE_RESIDUES = {"ARG", "LYS", "HIS", "ASP", "GLU", "CYS", "TYR"}


def fetch_pdb(pdb_id: str) -> str:
    """Download a PDB file from RCSB and return its contents as a string."""
    # Try the newer files endpoint first, then fall back
    urls = [
        f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb",
        f"https://www.rcsb.org/pdb/files/{pdb_id.upper()}.pdb",
    ]
    for url in urls:
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                print(f"Successfully fetched PDB file for {pdb_id.upper()} from:\n  {url}")
                return response.text
        except requests.RequestException as exc:
            print(f"Warning: request to {url} failed – {exc}")

    raise RuntimeError(
        f"Could not download PDB file for '{pdb_id}'. "
        "Check that the PDB ID is valid and that you have internet access."
    )


def parse_structure(pdb_id: str, pdb_text: str):
    """Parse PDB text with Biopython and return the Structure object."""
    parser = PDBParser(QUIET=True)
    handle = io.StringIO(pdb_text)
    structure = parser.get_structure(pdb_id.upper(), handle)
    return structure


def count_ionisable_residues(structure):
    """
    Walk through all chains in the structure and count ionisable residues.

    Returns
    -------
    residue_counts : dict  {residue_name: count}
    num_chains     : int   number of polypeptide chains (for terminus counting)
    """
    residue_counts = {name: 0 for name in IONISABLE_RESIDUES}
    num_chains = 0

    for model in structure:
        for chain in model:
            residues = [r for r in chain if r.id[0] == " "]  # skip HETATM / waters
            if not residues:
                continue
            num_chains += 1
            for residue in residues:
                resname = residue.get_resname().strip().upper()
                if resname in IONISABLE_RESIDUES:
                    residue_counts[resname] += 1
        break  # use only the first MODEL

    return residue_counts, num_chains


def henderson_hasselbalch_charge(pKa: float,
                                 pH: float,
                                 charge_below: float,
                                 charge_above: float) -> float:
    """
    Return the fractional charge of a single ionisable group at the given pH
    using the Henderson-Hasselbalch equation.

    fraction_protonated = 1 / (1 + 10^(pH - pKa))
    charge = fraction_protonated * charge_below + fraction_deprotonated * charge_above
    """
    fraction_protonated = 1.0 / (1.0 + 10 ** (pH - pKa))
    fraction_deprotonated = 1.0 - fraction_protonated
    return fraction_protonated * charge_below + fraction_deprotonated * charge_above


def calculate_charge(residue_counts: dict, num_chains: int, pH: float) -> float:
    """
    Calculate the overall estimated charge of the protein at the given pH.

    Parameters
    ----------
    residue_counts : dict   {residue_name: count}
    num_chains     : int    number of polypeptide chains
    pH             : float  pH value

    Returns
    -------
    float : estimated overall charge
    """
    total_charge = 0.0

    # Contributions from ionisable side-chains
    for resname, count in residue_counts.items():
        if count == 0:
            continue
        info = PKA_VALUES[resname]
        charge_per_residue = henderson_hasselbalch_charge(
            info["pKa"], pH, info["charge_below"], info["charge_above"]
        )
        total_charge += count * charge_per_residue

    # Contributions from N- and C-termini (one pair per chain)
    nterm_info = PKA_VALUES["NTERM"]
    cterm_info = PKA_VALUES["CTERM"]
    for _ in range(num_chains):
        total_charge += henderson_hasselbalch_charge(
            nterm_info["pKa"], pH, nterm_info["charge_below"], nterm_info["charge_above"]
        )
        total_charge += henderson_hasselbalch_charge(
            cterm_info["pKa"], pH, cterm_info["charge_below"], cterm_info["charge_above"]
        )

    return total_charge


def print_summary(pdb_id: str,
                  residue_counts: dict,
                  num_chains: int,
                  pH: float,
                  total_charge: float) -> None:
    """Print a nicely formatted summary."""
    print("\n" + "=" * 55)
    print(f"  Protein Charge Estimator")
    print(f"  PDB ID : {pdb_id.upper()}")
    print(f"  pH     : {pH}")
    print("=" * 55)
    print(f"\n  Polypeptide chains detected : {num_chains}")
    print("\n  Ionisable residue counts:")
    print(f"    {'Residue':<10} {'Count':>7}  {'pKa':>6}  {'Charge/residue':>15}")
    print("    " + "-" * 45)
    for resname in sorted(IONISABLE_RESIDUES):
        count = residue_counts.get(resname, 0)
        info  = PKA_VALUES[resname]
        c_per = henderson_hasselbalch_charge(
            info["pKa"], pH, info["charge_below"], info["charge_above"]
        )
        print(f"    {resname:<10} {count:>7}  {info['pKa']:>6.1f}  {c_per:>+15.4f}")

    # Termini rows
    for label, key in [("N-term", "NTERM"), ("C-term", "CTERM")]:
        info = PKA_VALUES[key]
        c_per = henderson_hasselbalch_charge(
            info["pKa"], pH, info["charge_below"], info["charge_above"]
        )
        print(f"    {label:<10} {num_chains:>7}  {info['pKa']:>6.1f}  {c_per:>+15.4f}")

    print("\n" + "=" * 55)
    print(f"  Estimated overall charge at pH {pH}: {total_charge:+.2f}")
    print("=" * 55 + "\n")


def main():
    # -----------------------------------------------------------------------
    # Get PDB ID from the command line or prompt the user
    # -----------------------------------------------------------------------
    if len(sys.argv) >= 2:
        pdb_id = sys.argv[1].strip()
    else:
        pdb_id = input("Enter PDB ID (e.g. 1CRN): ").strip()

    if len(sys.argv) >= 3:
        try:
            pH = float(sys.argv[2])
        except ValueError:
            print("Invalid pH value supplied; defaulting to 7.4")
            pH = 7.4
    else:
        ph_input = input("Enter pH (press Enter for default 7.4): ").strip()
        pH = float(ph_input) if ph_input else 7.4

    # -----------------------------------------------------------------------
    # Fetch, parse, count, calculate, display
    # -----------------------------------------------------------------------
    pdb_text = fetch_pdb(pdb_id)
    structure = parse_structure(pdb_id, pdb_text)
    residue_counts, num_chains = count_ionisable_residues(structure)
    total_charge = calculate_charge(residue_counts, num_chains, pH)
    print_summary(pdb_id, residue_counts, num_chains, pH, total_charge)


if __name__ == "__main__":
    main()
