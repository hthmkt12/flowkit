export function createDebuggerLeaseManager() {
  const leases = new Map();
  return {
    acquire(tabId, owner) {
      if (leases.has(tabId)) throw new Error('debugger lease busy');
      const lease = { tabId, owner, generation: 1, active: true };
      leases.set(tabId, lease);
      return { ...lease };
    },
    release(tabId, owner) {
      const lease = leases.get(tabId);
      if (!lease || lease.owner !== owner) return false;
      leases.delete(tabId);
      return true;
    },
    reconcile(tabId, owner) {
      const lease = leases.get(tabId);
      if (!lease || lease.owner !== owner) return { active: false, reason: 'stale_or_missing' };
      return { active: true, generation: lease.generation };
    },
  };
}
