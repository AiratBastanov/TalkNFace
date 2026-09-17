"""Read only public language fields, emit aggregate English pattern counts only."""
import re
from core import ROOT, HERE, read, write, digest

PATTERNS = {
 'preference_probing': r'\b(?:what|which).{0,65}\b(?:prefer|important|need|priority|want)\b',
 'bargaining_proposal': r'\b(?:how about|would you|i can offer|i could offer|can we|i propose)\b',
 'need_or_reason': r'\b(?:because|i need|we need|due to|so that)\b',
 'coordination': r'\b(?:work together|both of us|we can|let us|let\'s|agreement|agree on)\b',
 'concession_structure': r'\b(?:willing to|in return|compromise|instead|if you|in exchange)\b',
 'multi_issue_link': r'\b(?:and|but|if|while)\b.{0,100}\b(?:and|but|if|while)\b',
}


def main():
    manifest=read(ROOT/'docs/gates/evidence/AI_LOCAL_DATASET_MANIFEST.json')
    results=[]
    for source,relative,field in [('CaSiNo','AlagDatasets/raw/casino/data/casino.json','chat_logs'),
                                   ('Job Interview Negotiation','AlagDatasets/raw/job-interview/data.json','comments')]:
        path=ROOT/relative
        raw=path.read_bytes()
        artifact=next(x for x in manifest['raw_artifacts'] if x['relative_local_path']==relative)
        if digest(raw)!=artifact['sha256']:
            raise ValueError('RAW_INTEGRITY_DRIFT')
        data=read(path)
        texts=[x['text' if field=='chat_logs' else 'body'] for d in data for x in d[field]]
        texts=[t for t in texts if isinstance(t,str) and t.strip() and t not in ('Submit-Deal','Accept-Deal','Reject-Deal','Walk-Away')]
        metadata=next(x for x in manifest['sources'] if x['dataset_name']==source)
        results.append(dict(dataset=source,source_repository=metadata['source_repository'],revision=metadata['revision'],
                            paper=metadata['paper'],source_license=metadata['license'],raw_sha256=artifact['sha256'],
                            utterances_scanned=len(texts),categories={name:sum(bool(re.search(pattern,t,re.I)) for t in texts)
                                                                    for name,pattern in PATTERNS.items()}))
    write(HERE/'linguistic_patterns.json',dict(method='Overlapping case-insensitive bounded regex counts; research patterns, not dialogue-act labels',
          patterns=PATTERNS,sources=results,source_text_stored=False,source_labels_converted=False,
          translations_created=0,raw_conversation_ids_stored=False,
          influence='Pattern categories motivated independently authored probing, reason, exchange and multi-issue constructions; no source utterance was shown to the author or copied.',
          limitations='Regexes are coarse linguistic indicators, not exhaustive or gold strategy annotation. Counts may overlap.',
          synthetic_license_status='NOT_ASSIGNED'))
    print('Aggregate linguistic pattern audit complete; no source utterances exported.')


if __name__=='__main__':
    main()
