(function(){
  const chatToggle=document.createElement('button');
  chatToggle.id='chat-toggle';
  chatToggle.textContent='Chat';
  chatToggle.style.position='fixed';
  chatToggle.style.bottom='20px';
  chatToggle.style.right='20px';
  chatToggle.style.zIndex='1000';
  document.body.appendChild(chatToggle);

  const chatBox=document.createElement('div');
  chatBox.id='chat-box';
  chatBox.style.position='fixed';
  chatBox.style.bottom='60px';
  chatBox.style.right='20px';
  chatBox.style.width='300px';
  chatBox.style.maxHeight='400px';
  chatBox.style.background='white';
  chatBox.style.border='1px solid #ccc';
  chatBox.style.borderRadius='8px';
  chatBox.style.display='none';
  chatBox.style.flexDirection='column';
  chatBox.style.fontSize='14px';
  chatBox.innerHTML='<div id="chat-messages" style="flex-grow:1;overflow-y:auto;padding:8px;"></div><form id="chat-form"><input type="text" id="chat-input" style="width:100%;box-sizing:border-box;padding:8px;" autocomplete="off" placeholder="Ask me..."/></form>';
  document.body.appendChild(chatBox);

  chatToggle.addEventListener('click',()=>{
    chatBox.style.display=chatBox.style.display==='none'?'flex':'none';
  });

  document.getElementById('chat-form').addEventListener('submit',async(e)=>{
    e.preventDefault();
    const input=document.getElementById('chat-input');
    const message=input.value.trim();
    if(!message) return;
    appendMessage('You',message);
    input.value='';
    try{
      const resp=await fetch('/mcp-chat/',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message})});
      if(resp.ok){
        const data=await resp.json();
        appendMessage('Bot',data.reply);
      }else{
        appendMessage('Bot','Error: '+resp.statusText);
      }
    }catch(err){
      appendMessage('Bot','Error sending message');
    }
  });

  function appendMessage(sender,text){
    const msgContainer=document.getElementById('chat-messages');
    const div=document.createElement('div');
    div.textContent=sender+': '+text;
    div.style.marginBottom='4px';
    msgContainer.appendChild(div);
    msgContainer.scrollTop=msgContainer.scrollHeight;
  }
})();
