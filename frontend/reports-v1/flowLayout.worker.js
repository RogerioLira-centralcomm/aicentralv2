import ELK from 'elkjs/lib/elk.bundled.js';
const elk=new ELK();
self.onmessage=async({data})=>{try{self.postMessage({graph:await elk.layout(data)});}catch(error){self.postMessage({error:error.message});}};
