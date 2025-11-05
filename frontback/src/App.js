import React, {useEffect, useState} from 'react';
import axios from 'axios';
import Plot from 'react-plotly.js';
import Inventory from './components/Inventory';
import './styles.css';

function App(){
  const [filters, setFilters] = useState(null);
  const [chartData, setChartData] = useState(null);
  const [files, setFiles] = useState([]);
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [page, setPage] = useState('sales');
  const [inventoryData, setInventoryData] = useState(null);
  const [invMonth, setInvMonth] = useState('');

  useEffect(()=>{
    // try to load filters if backend already has data
    axios.get('http://localhost:5001/api/filters').then(r=>setFilters(r.data)).catch(()=>{});
  },[])

  const upload = async ()=>{
    if(files.length===0) return alert('Select files to upload');
    const fd = new FormData();
    for(let f of files) fd.append('files', f);
    const res = await axios.post('http://localhost:5001/api/upload', fd, {headers:{'Content-Type':'multipart/form-data'}})
    alert('Upload result: '+JSON.stringify(res.data));
    // refresh filters
    const rf = await axios.get('http://localhost:5001/api/filters');
    setFilters(rf.data);
    if(rf.data.dates && rf.data.dates.length) {
      setStart(rf.data.dates[0]);
      setEnd(rf.data.dates[rf.data.dates.length-1]);
    }
  }

  const loadChart = async ()=>{
    if(!filters) return alert('No filters available');
    const payload = {start, end, regions: ['ALL Region'], countries: ['ALL Country'], products: ['ALL Product Type'], aggregation: 'monthly', currency:'RMB'};
    const r = await axios.post('http://localhost:5001/api/chart-data', payload);
    setChartData(r.data);
  }

  const loadInventory = async (month) => {
    if(!month) return alert('Select month');
    try{
      const r = await axios.get('http://localhost:5001/api/inventory-cards', { params: { month } });
      setInventoryData(r.data);
    }catch(err){
      console.error(err);
      alert('Failed to load inventory');
    }
  }

  return (
    <div>
      {/* Sidebar background (mimic original Dash layout) */}
      <div id="sidebar-background-color" style={{position:'fixed', top:0, left:0, width:400, height:'100vh', backgroundColor:'#D3D3D3', zIndex:0}} />

      <div style={{minHeight:'100vh', position:'relative', overflow:'hidden'}}>
        <div className="upload-area">
          <input id="upload-input" type="file" multiple onChange={(e)=>setFiles(e.target.files)} style={{display:'none'}} />
          <label htmlFor="upload-input" style={{cursor:'pointer'}}>
            {/* try to reuse existing logo path; if missing the broken image is non-fatal */}
            <img src="/assets/Logo2.jpg" alt="logo" className="upload-logo" />
          </label>
          <button className="small-button" onClick={upload} style={{marginLeft:12}}>Upload</button>
        </div>

  <div id="main-content" style={{position:'relative', zIndex:2, padding:20, marginLeft:420, backgroundColor:'#fff', minHeight:'100vh'}}>
          <div style={{display:'flex', alignItems:'center', gap:12}}>
            <h2 style={{color:'#000'}}>Fina Dashboard</h2>
            <div>
              <button className="small-button" onClick={()=>setPage('sales')} style={{marginRight:8}}>Sales</button>
              <button className="small-button" onClick={()=>setPage('inventory')}>Inventory</button>
            </div>
          </div>

          {/* Filters area */}
          {filters && (
            <div style={{marginTop:12, marginBottom:16, display:'flex', alignItems:'center', gap:12}}>
              <div>
                <label style={{display:'block', fontWeight:'600', color:'#000'}}>Start</label>
                <select value={start} onChange={(e)=>setStart(e.target.value)}>
                  {filters.dates.map(d=> <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <div>
                <label style={{display:'block', fontWeight:'600', color:'#000'}}>End</label>
                <select value={end} onChange={(e)=>setEnd(e.target.value)}>
                  {filters.dates.map(d=> <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
              <div style={{alignSelf:'flex-end'}}>
                <button className="small-button" onClick={loadChart}>Load Charts</button>
              </div>

              {page === 'inventory' && (
                <>
                  <div>
                    <label style={{display:'block', fontWeight:'600', color:'#000'}}>Inventory Month</label>
                    <select value={invMonth} onChange={(e)=>setInvMonth(e.target.value)}>
                      <option value="">-- select --</option>
                      {filters.dates.map(d=> <option key={d} value={d}>{d}</option>)}
                    </select>
                  </div>
                  <div style={{alignSelf:'flex-end'}}>
                    <button className="small-button" onClick={()=>loadInventory(invMonth)}>Load Inventory</button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Page content */}
          {page === 'sales' && chartData && (
            <div style={{display:'flex', gap:20, flexWrap:'wrap'}}>
              <Plot
                data={[{x: chartData.x, y: chartData.adj_sales, type: 'scatter', mode: 'lines+markers', name:'Sales'}]}
                layout={{width:600, height:400, title:'Adj Sales Amount'}}
              />
              <Plot
                data={[{x: chartData.x, y: chartData.sales_qua, type: 'scatter', mode: 'lines+markers', name:'Sales Qua'}]}
                layout={{width:600, height:400, title:'Sales Quantity'}}
              />
            </div>
          )}

          {page === 'inventory' && (
            <Inventory data={inventoryData} />
          )}
        </div>
      </div>
    </div>
  )
}

export default App;