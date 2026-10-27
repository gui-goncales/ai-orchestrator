document.getElementById('extension-id').textContent = chrome.runtime.id;
document.getElementById('connect').onclick = async () => {
 const status = document.getElementById('status');
 try {
  const [tab] = await chrome.tabs.query({active:true,currentWindow:true});
  if (!tab?.id || new URL(tab.url).origin !== 'https://chatgpt.com') throw Error('Abra uma aba em https://chatgpt.com e tente novamente.');
  await chrome.storage.local.set({chatgptTabId:tab.id});
  status.textContent = 'Aba conectada. Cole o ID no orquestrador e clique em Verificar.';
 } catch (error) {status.textContent = error.message;}
};
