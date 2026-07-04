# Request #1: write me a program to convert a dna sequence into its amino acid sequence
# Completed with 2 subtask(s)

# DNA to Amino Acid Sequence Converter

def dna_to_mrna(dna_sequence):
    """
    Transcribe a DNA sequence to an mRNA sequence.
    Replaces T (Thymine) with U (Uracil).
    """
    return dna_sequence.upper().replace('T', 'U')


def translate_mrna_to_protein(mrna_sequence):
    """
    Translate an mRNA sequence into an amino acid (protein) sequence.
    Translation stops at a stop codon or end of sequence.
    """
    # Full standard genetic codon table (mRNA codons -> amino acids)
    codon_table = {
        "UUU": "F", "UUC": "F",  # Phenylalanine
        "UUA": "L", "UUG": "L",  # Leucine
        "CUU": "L", "CUC": "L", "CUA": "L", "CUG": "L",  # Leucine
        "AUU": "I", "AUC": "I", "AUA": "I",               # Isoleucine
        "AUG": "M",                                         # Methionine (Start)
        "GUU": "V", "GUC": "V", "GUA": "V", "GUG": "V",  # Valine
        "UCU": "S", "UCC": "S", "UCA": "S", "UCG": "S",  # Serine
        "CCU": "P", "CCC": "P", "CCA": "P", "CCG": "P",  # Proline
        "ACU": "T", "ACC": "T", "ACA": "T", "ACG": "T",  # Threonine
        "GCU": "A", "GCC": "A", "GCA": "A", "GCG": "A",  # Alanine
        "UAU": "Y", "UAC": "Y",                            # Tyrosine
        "UAA": "*", "UAG": "*", "UGA": "*",                # Stop codons
        "CAU": "H", "CAC": "H",                            # Histidine
        "CAA": "Q", "CAG": "Q",                            # Glutamine
        "AAU": "N", "AAC": "N",                            # Asparagine
        "AAA": "K", "AAG": "K",                            # Lysine
        "GAU": "D", "GAC": "D",                            # Aspartic Acid
        "GAA": "E", "GAG": "E",                            # Glutamic Acid
        "UGU": "C", "UGC": "C",                            # Cysteine
        "UGG": "W",                                         # Tryptophan
        "CGU": "R", "CGC": "R", "CGA": "R", "CGG": "R",  # Arginine
        "AGU": "S", "AGC": "S",                            # Serine
        "AGA": "R", "AGG": "R",                            # Arginine
        "GGU": "G", "GGC": "G", "GGA": "G", "GGG": "G",  # Glycine
    }

    protein_sequence = []

    for i in range(0, len(mrna_sequence) - 2, 3):
        codon = mrna_sequence[i:i+3]
        if len(codon) < 3:
            break  # Incomplete codon at end; skip it
        amino_acid = codon_table.get(codon, None)
        if amino_acid is None:
            print(f"  Warning: Unknown codon '{codon}' encountered. Skipping.")
            continue
        if amino_acid == "*":
            print(f"  Stop codon '{codon}' encountered. Translation complete.")
            break
        protein_sequence.append(amino_acid)

    return protein_sequence


def dna_to_protein(dna_sequence):
    """
    Full pipeline: DNA -> mRNA -> Protein (amino acid sequence).
    """
    dna_sequence = dna_sequence.upper().strip()

    # Validate the DNA sequence
    valid_bases = set('ATCG')
    invalid_chars = set(dna_sequence) - valid_bases
    if invalid_chars:
        raise ValueError(f"Invalid characters in DNA sequence: {invalid_chars}. "
                         f"Only A, T, C, G are allowed.")

    if len(dna_sequence) < 3:
        raise ValueError("DNA sequence is too short. Must be at least 3 nucleotides.")

    print(f"\n  DNA Sequence    : {dna_sequence}")

    # Step 1: Transcribe DNA to mRNA
    mrna_sequence = dna_to_mrna(dna_sequence)
    print(f"  mRNA Sequence   : {mrna_sequence}")

    # Step 2: Translate mRNA to protein
    protein = translate_mrna_to_protein(mrna_sequence)
    return protein


def main():
    print("=" * 55)
    print("       DNA to Amino Acid Sequence Converter")
    print("=" * 55)

    while True:
        dna_input = input("\nEnter a DNA sequence (or 'quit' to exit): ").strip()

        if dna_input.lower() == 'quit':
            print("Goodbye!")
            break

        try:
            protein_sequence = dna_to_protein(dna_input)

            if protein_sequence:
                protein_str = "".join(protein_sequence)
                print(f"\n  Amino Acid Sequence ({len(protein_sequence)} residues):")
                print(f"  {protein_str}")
            else:
                print("\n  No amino acids were translated (check for immediate stop codon or short sequence).")

        except ValueError as e:
            print(f"\n  Error: {e}")

        print()


if __name__ == "__main__":
    # --- Run a quick built-in demo first ---
    print("=== Built-in Demo ===")
    demo_sequences = [
        ("ATGGCCATTGTAATGGGCCGCTGAAAGGGTGCCCGATAG", "Demo 1 (with stop codon)"),
        ("ATGCGT",                                   "Demo 2 (short sequence)"),
        ("TTTTTT",                                   "Demo 3 (no start codon)"),
    ]

    for seq, label in demo_sequences:
        print(f"\n[{label}]")
        try:
            result = dna_to_protein(seq)
            if result:
                print(f"  Protein: {''.join(result)}")
            else:
                print("  Protein: (empty)")
        except ValueError as e:
            print(f"  Error: {e}")

    print("\n" + "=" * 55)
    print("  Now entering interactive mode...")
    print("=" * 55)

    # --- Interactive mode ---
    main()