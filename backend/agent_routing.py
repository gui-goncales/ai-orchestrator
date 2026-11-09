"""Shared provider eligibility for initial routing and recovery."""


def exclusion_reason(provider):
    if provider.get('id') not in ('codex', 'antigravity') and not provider.get('automatic_routing'):
        return 'Provedor não habilitado para seleção automática'
    if provider.get('id') in ('rea', 'gemini'):
        return 'Ferramenta estática ou provedor legado não é substituto automático'
    if not provider.get('installed'):
        return 'Provedor não instalado'
    if provider.get('automatic_routing_blocked'):
        return 'Seleção automática bloqueada por falha recente'
    if provider.get('state') not in ('available', 'ready'):
        return 'Provedor indisponível ou sem autenticação validada'
    return None
