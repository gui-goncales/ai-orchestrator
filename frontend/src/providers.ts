export type ProviderStatus = {
  id: string;
  installed: boolean;
  state: string;
  automatic_routing?: boolean;
  automatic_routing_blocked?: boolean;
};

export function isProviderReady(provider: ProviderStatus) {
  return provider.installed && provider.state === 'available';
}

export function isChatProviderReady(provider: ProviderStatus) {
  return provider.id !== 'rea' && isProviderReady(provider);
}

export function canRouteAutomatically(provider: ProviderStatus) {
  return isChatProviderReady(provider) && !provider.automatic_routing_blocked &&
    (['codex', 'antigravity'].includes(provider.id) || provider.automatic_routing === true);
}
