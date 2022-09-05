# coding: utf-8

def tokenize_file(file_name, ignore_comments=False):
    lines = []
    with open(file_name) as f:
        lines = f.read().split("\n")
    # cut whitespace
    lines = [line.strip() for line in lines]
    # remove empty lines
    lines = [
        line
        for line in lines
        if line and (
            ignore_comments or not line.startswith("#")
        )
    ]
    return lines
