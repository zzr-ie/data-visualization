import React, {useMemo, useState} from 'react';
import Plot from 'react-plotly.js';

function Card({title, value, valueAmt, mom}){
  return (
    <div className="card-container" style={{padding:12, minWidth:220}}>
      <div className="card-header">{title}</div>
      <div style={{padding:12, textAlign:'center'}}>
        <div style={{fontSize:18, fontWeight:700, color:'#111'}}>{value === null || value === undefined ? '—' : value}</div>
        {valueAmt !== undefined && <div style={{fontSize:12, color:'#444', marginTop:6}}>Value: {Number(valueAmt).toLocaleString()}</div>}
        {mom !== undefined && mom !== null && <div style={{fontSize:12, color: mom>=0? '#0a7d3a':'#b22222', marginTop:6}}>MoM: {(mom*100).toFixed(1)}%</div>}
      </div>
    </div>
  )
}

export default function Inventory({data}){
  if(!data) return <div style={{padding:20, color:'#000'}}>No inventory data loaded</div>

  const cards = data.cards || [];
  const breakdown = data.cost_breakdown || [];
  const top_items = data.top_items || [];

  const coverage_distribution = data.coverage_distribution || [];

  // sorting for top items table
  const [sortKey, setSortKey] = useState('value');
  const [sortDir, setSortDir] = useState('desc');

  const sortedTopItems = useMemo(() => {
    if(!top_items || top_items.length === 0) return [];
    const arr = [...top_items];
    arr.sort((a,b)=>{
      const va = a[sortKey] == null ? -Infinity : a[sortKey];
      const vb = b[sortKey] == null ? -Infinity : b[sortKey];
      if(va === vb) return 0;
      return (va > vb ? 1 : -1) * (sortDir === 'asc' ? 1 : -1);
    });
    return arr;
  }, [top_items, sortKey, sortDir]);

  function toggleSort(key){
    if(sortKey === key){
      setSortDir(d=> d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  }

  const coverageCard = cards.find(c=>c.id==='coverage');

  return (
    <div style={{padding:12}}>
      <div className="inv-card-container inventory-overview">
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', padding:12}}>
          <div>
            <div className="card-title">Inventory Summary</div>
            <div style={{color:'#333'}}>{data.month || 'All'}</div>
          </div>
        </div>
      </div>

      <div className="inventory-cards-row" style={{marginTop:8}}>
        {cards.map(c=> <Card key={c.id} title={c.title} value={c.value} valueAmt={c.value_amt} mom={c.mom_qty} />)}
      </div>

      <div style={{display:'flex', gap:20, alignItems:'flex-start', marginTop:18}}>
        <div className="inventory-left">
          <div className="card-container" style={{padding:12}}>
            <div className="card-header">Cost Breakdown</div>
            <div style={{padding:12}}>
              {breakdown.length>0 ? (
                <>
                  <Plot
                    data={[{x: breakdown.map(r=>r.Category), y: breakdown.map(r=>r['Absolute Value']), type:'bar', marker:{color:'#2a9df4'}}]}
                    layout={{width:700,height:280,margin:{t:30,l:40,r:20,b:40}}}
                  />
                  {/* pie chart using Percentage if available, fallback to Absolute Value */}
                  <Plot
                    data={[{labels: breakdown.map(r=>r.Category), values: breakdown.map(r=> r.Percentage != null ? r.Percentage : r['Absolute Value']), type:'pie'}]}
                    layout={{width:400,height:260,margin:{t:10,l:10,r:10,b:10}}}
                  />
                </>
              ) : (
                <div style={{padding:16}}>No cost breakdown available</div>
              )}
            </div>
          </div>

          <div className="card-container" style={{padding:12, marginTop:12}}>
            <div className="card-header">Top Items by Inventory Value</div>
            <div style={{padding:12}}>
              {top_items.length>0 ? (
                <>
                  <div style={{marginBottom:8}}>
                    <small style={{color:'#666'}}>Click column headers to sort</small>
                  </div>
                  <table className="top-items-table">
                    <thead>
                      <tr>
                        <th onClick={()=>toggleSort('item')} style={{cursor:'pointer'}}>Item {sortKey==='item' ? (sortDir==='asc' ? '▲':'▼') : ''}</th>
                        <th onClick={()=>toggleSort('on_hand')} style={{cursor:'pointer'}}>On-hand {sortKey==='on_hand' ? (sortDir==='asc' ? '▲':'▼') : ''}</th>
                        <th onClick={()=>toggleSort('value')} style={{cursor:'pointer'}}>Value {sortKey==='value' ? (sortDir==='asc' ? '▲':'▼') : ''}</th>
                        <th onClick={()=>toggleSort('coverage')} style={{cursor:'pointer'}}>Coverage (m) {sortKey==='coverage' ? (sortDir==='asc' ? '▲':'▼') : ''}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedTopItems.map((it, idx)=> (
                        <tr key={idx}>
                          <td>{it.item || it.id}</td>
                          <td>{it.on_hand != null ? Number(it.on_hand).toLocaleString() : '—'}</td>
                          <td>{it.value != null ? Number(it.value).toLocaleString() : '—'}</td>
                          <td>{it.coverage != null ? Number(it.coverage).toFixed(1) : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              ) : (
                <div>No top items available</div>
              )}
            </div>
          </div>
        </div>

        <div className="inventory-right">
          <div className="card-container" style={{padding:12}}>
            <div className="card-header">Coverage</div>
            <div style={{padding:12}}>
              {coverageCard && coverageCard.value ? (
                <div style={{padding:12, background:'#fff', borderRadius:8}}>
                  <div style={{fontSize:12,color:'#666'}}>Median coverage (months)</div>
                  <div style={{fontSize:20,fontWeight:700}}>{Number(coverageCard.value).toFixed(1)}</div>
                </div>
              ) : (
                <div>No coverage distribution available</div>
              )}
            </div>
          </div>

          <div className="card-container" style={{padding:12, marginTop:12}}>
            <div className="card-header">Quick Actions</div>
            <div style={{padding:12, display:'flex', flexDirection:'column', gap:8}}>
              <button className="small-button" onClick={()=>window.alert('Export not implemented')}>Export Inventory CSV</button>
              <button className="small-button" onClick={()=>window.alert('Filter not implemented')}>Filter by Category</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
