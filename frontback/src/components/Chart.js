import React from 'react';
import Plot from 'react-plotly.js';

export default function Chart({x,y, title}){
  return <Plot data={[{x,y,type:'scatter',mode:'lines+markers'}]} layout={{width:600,height:400,title}} />
}
