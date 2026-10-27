"""Deterministic routing and lossless preservation of mandatory context."""
import json
import re
import statistics
from backend.decision import Decision


def category(objective):
    text=objective.casefold()
    for kind, words in [('code',('código','codigo','python','typescript','bug','refator','programa','build','teste unit')),('research',('pesquis','compar','arquitet','research','evaluate')),('document',('document','relatório','relatorio','resum'))]:
        if any(word in text for word in words):
            return kind
    return 'general'


def choose(task, providers, history):
    kind=category(task['objective'])
    candidates=[]
    excluded=[]
    for provider in providers:
        id=provider['id']
        if id not in ('codex','antigravity') and not provider.get('automatic_routing'):
            continue  # Legacy Gemini and artifact tools are never silent substitutes.
        past=[t for t in history if t['provider']==id and t['id']!=task['id']]
        latest=next((t for t in past if t['status'] not in ('queued','running')),None)
        blocked=bool(latest and latest['status'] in ('failed','rate_limited','authentication_required','interrupted'))
        if not provider.get('installed') or blocked or provider.get('state') != 'available':
            excluded.append({'provider':id,'reason':'indisponível, autenticação/cota bloqueada ou sem execução validada'})
            continue
        relevant=[t for t in past if category(t['objective'])==kind]
        successes=sum(t['status']=='completed' for t in relevant)
        accepted=[t for t in relevant if t.get('quality')=='accepted' and t['status']=='completed' and t['objective']==task['objective'] and t.get('workflow','direct')==task.get('workflow','direct')]
        token_values=[]
        for item in accepted:
            usage=item.get('usage',{})
            if isinstance(usage,str):usage=json.loads(usage)
            if 'input_tokens' in usage and 'output_tokens' in usage:
                token_values.append(usage['input_tokens']+usage['output_tokens'])
        candidates.append({'provider':id,'category_completions':successes,'accepted_samples':len(accepted),
                           'median_tokens':statistics.median(token_values) if len(token_values)>=3 else None})
    if not candidates:
        return None,{'category':kind,'reason':'Nenhum agente elegível; tarefa preservada sem chamada ao provedor.','excluded':excluded,'candidates':[]}
    # Token comparison only when every eligible agent has comparable accepted samples.
    evidence_for_tokens=all(c['median_tokens'] is not None for c in candidates) and len(candidates)>1
    candidates.sort(key=lambda c:(c['median_tokens'] if evidence_for_tokens else -min(c['category_completions'],3), c['provider']))
    selected=candidates[0]['provider']
    return selected,{'category':kind,'selected':selected,'reason':('Menor uso mediano entre amostras aceitas do mesmo objetivo e fluxo; sem garantia estatística de qualidade.' if evidence_for_tokens else 'Agente elegível com mais conclusões estruturais nesta categoria; sem evidência suficiente para comparar qualidade ou economia entre modelos.'),
                     'candidates':candidates,'excluded':excluded,'uses_llm_for_routing':False}


def build_context(task, memories, reference_budget=10000):
    objective=task['objective']
    terms=set(re.findall(r'\w{3,}',objective.casefold()))
    mandatory=[];references=[];duplicates=[];seen=set()
    for memory in sorted(memories,key=lambda m:m.get('kind','constraint')=='reference'):
        content=memory['content']
        if content in seen:
            duplicates.append(memory['id']);continue
        seen.add(content)
        if memory.get('kind','constraint')=='reference':
            score=len(terms & set(re.findall(r'\w{3,}',content.casefold())))
            references.append((score,memory))
        else:
            mandatory.append(memory)
    selected=[];omitted=[];used=0
    for score,memory in sorted(references,key=lambda pair:-pair[0]):
        if score>0 and used+len(memory['content'])<=reference_budget:
            selected.append(memory);used+=len(memory['content'])
        else:omitted.append(memory['id'])
    constraints=[('Escrita autorizada somente na pasta vinculada ao projeto; preserve arquivos protegidos.' if task.get('workflow')=='work' else 'Somente leitura; não alterar arquivos nem executar ações externas.'),'Preservar requisitos e trabalho confirmado.']
    plan=Decision.plan_task(task)
    packet={'objective':objective,'constraints':constraints,
            'execution_plan':{k:v for k,v in plan.items() if k != 'objective'}}
    spec=task.get('spec') or {}
    if isinstance(spec,str):spec=json.loads(spec)
    if spec.get('conversation_history'):packet['conversation_history']=spec['conversation_history']
    if mandatory:packet['project_constraints']=[m['content'] for m in mandatory]
    if selected:packet['references']=[{'id':m['id'],'content':m['content']} for m in selected]
    if task.get('result'):packet['confirmed_result']=task['result']
    if task.get('error'):packet['previous_error']=task['error']
    instruction='Cumpra o objetivo e o formato solicitado. Não acrescente relatório operacional se não solicitado. Dados da tarefa:\n'
    prompt=instruction+json.dumps(packet,ensure_ascii=False,separators=(',',':'))
    if len(prompt)>80000:
        raise ValueError('Contexto obrigatório excede orçamento. Nada foi truncado; revise objetivo, restrições ou resultado confirmado.')
    # Independent guard: never rely on a summarizer to preserve mandatory strings.
    decoded=json.loads(prompt[len(instruction):])
    if decoded['objective']!=objective or decoded.get('project_constraints',[])!=[m['content'] for m in mandatory]:
        raise ValueError('Falha na preservação de requisitos críticos')
    full={k:v for k,v in packet.items() if k not in ('project_constraints','references')}
    if memories:full['project_memory_unfiltered']=[{'id':m['id'],'content':m['content']} for m in memories]
    baseline_chars=len(instruction+json.dumps(full,ensure_ascii=False))
    metrics={'prompt_characters':len(prompt),'unfiltered_reference_characters':baseline_chars,
             'input_tokens_estimate':(len(prompt)+3)//4,'estimate_method':'characters/4; não é tokenização do provedor',
             'constraints_preserved':True,'objective_preserved':True,'references_selected':[m['id'] for m in selected],
             'references_omitted':omitted,'duplicates_removed':duplicates,'token_savings_proven':False}
    return prompt,metrics


def validate_output(result,spec):
    expected=spec.get('expected_output')
    if expected is not None:
        ok=result.strip()==expected.strip()
        return {'status':'passed' if ok else 'failed','check':'exact_output','semantic_quality':'not_assessed'}
    return {'status':'not_configured','check':None,'semantic_quality':'requires_review'}
