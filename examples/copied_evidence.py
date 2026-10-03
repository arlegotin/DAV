"""Illustrate shared evidence with a toy distribution; no empirical claim."""
import argparse
import json

import numpy as np

from depverify.probability import posterior_correct


def demonstration():
    copied=np.zeros((2,3,3,3,3))
    copied[1,0,0,2,2],copied[1,1,1,2,2]=.4,.1
    copied[0,0,0,2,2],copied[0,1,1,2,2]=.1,.4
    independent=np.zeros_like(copied)
    for y,probabilities in [(0,(.2,.8)),(1,(.8,.2))]:
        for a in range(2):
            for b in range(2):
                independent[y,a,b,2,2]=.5*probabilities[a]*probabilities[b]
    return {'one_pass':posterior_correct(copied,('PASS',None,None,None)),
            'copied_passes':posterior_correct(copied,('PASS','PASS',None,None)),
            'independent_passes':posterior_correct(independent,('PASS','PASS',None,None))}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json',action='store_true')
    args=parser.parse_args()
    result=demonstration()
    if args.json:print(json.dumps(result,sort_keys=True))
    else:
        print('Toy prior: 50% correct; each review is 80% accurate.')
        print(f"One PASS: {result['one_pass']:.1%} probability of correctness.")
        print(f"Two copied PASSes: {result['copied_passes']:.1%}.")
        print(f"Two independent PASSes: {result['independent_passes']:.1%}.")
        print('The copied review adds no information. These are constructed probabilities, not model results.')
