import { useState, useEffect } from 'react';

type Lead = {
  id: number;
  subreddit: string;
  url: string;
  title: string;
  proposal: string;
  has_video: boolean;
  video_path: string;
  contacted: boolean;
};

function App() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [pitchingId, setPitchingId] = useState<number | null>(null);
  const [selectedLeads, setSelectedLeads] = useState<number[]>([]);
  
  const [manualUrl, setManualUrl] = useState("");
  const [manualStyle, setManualStyle] = useState("DEFAULT");
  const [manualLoading, setManualLoading] = useState(false);
  
  const [activeTab, setActiveTab] = useState<'CRM' | 'GALLERY'>('CRM');
  const [galleryVideos, setGalleryVideos] = useState<any[]>([]);
  
  useEffect(() => {
    fetch('/api/leads')
      .then(res => res.json())
      .then(data => {
        setLeads(data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  const handlePitch = async (row_index: number) => {
    // Open a blank window immediately before the async call to bypass browser popup blockers
    const popup = window.open('about:blank', '_blank');
    
    setPitchingId(row_index);
    try {
      const res = await fetch('/api/generate-pitch-url', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ row_index })
      });
      const data = await res.json();
      
      if (data.success) {
        // Redirect the blank popup to the actual Reddit compose URL
        if (popup) {
          popup.location.href = data.compose_url;
        }
        
        // Refresh leads to show as contacted
        const updated = await fetch('/api/leads').then(r => r.json());
        setLeads(updated);
      } else {
        if (popup) popup.close();
        alert("Failed: " + data.detail);
      }
    } catch (err) {
      if (popup) popup.close();
      alert("Error generating pitch URL");
    }
    setPitchingId(null);
  };

  const handleClearLeads = async () => {
    const isClearingAll = selectedLeads.length === 0;
    const msg = isClearingAll 
      ? "Are you sure you want to clear ALL leads? This cannot be undone." 
      : `Are you sure you want to clear ${selectedLeads.length} selected leads?`;
      
    if (confirm(msg)) {
      try {
        await fetch('/api/leads/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ indices: selectedLeads })
        });
        const updated = await fetch('/api/leads').then(r => r.json());
        setLeads(updated);
        setSelectedLeads([]);
      } catch (err) {
        alert("Error clearing leads");
      }
    }
  };

  const toggleLeadSelection = (index: number) => {
    setSelectedLeads(prev => 
      prev.includes(index) ? prev.filter(i => i !== index) : [...prev, index]
    );
  };

  const handleManualClip = async () => {
    if (!manualUrl) return;
    setManualLoading(true);
    try {
      const res = await fetch('/api/manual-clip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: manualUrl, style: manualStyle })
      });
      const data = await res.json();
      if (data.success) {
        alert("Manual clip started! The agent is rendering it in the background. It will appear here shortly.");
        setManualUrl("");
      } else {
        alert("Error: " + data.message);
      }
    } catch (err) {
      alert("Failed to start manual clip.");
    }
    setManualLoading(false);
  };

  const fetchGallery = async () => {
    try {
      const res = await fetch('/api/gallery');
      const data = await res.json();
      if (Array.isArray(data)) {
        setGalleryVideos(data);
      } else {
        console.error("Gallery API returned non-array:", data);
        setGalleryVideos([]);
      }
    } catch (err) {
      console.error("Gallery fetch failed:", err);
      setGalleryVideos([]);
    }
  };

  if (loading) return <div className="p-10 text-center text-xl font-bold">Loading Agency Backend...</div>;

  const validLeads = leads;

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-6xl mx-auto">
        <header className="mb-8 flex flex-col space-y-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-4xl font-extrabold text-gray-900 tracking-tight">Clipping Agency Dashboard</h1>
              <p className="text-gray-500 mt-2">Manage your automated outreach and client acquisition.</p>
            </div>
            <div className="flex items-center space-x-4">
              <button 
                onClick={handleClearLeads}
                className="bg-red-100 text-red-600 hover:bg-red-200 px-4 py-2 rounded-lg font-semibold shadow transition-colors"
              >
                {selectedLeads.length > 0 ? `Clear Selected (${selectedLeads.length})` : 'Clear All Leads'}
              </button>
              <div className="bg-blue-600 text-white px-4 py-2 rounded-lg font-semibold shadow">
                {validLeads.length} Leads Ready
              </div>
            </div>
          </div>
          
          <div className="bg-white p-5 rounded-xl shadow-sm border border-gray-200 flex flex-col md:flex-row gap-4 items-end">
            <div className="flex-1 w-full">
              <label className="block text-sm font-bold text-gray-700 mb-1">Manual Video URL</label>
              <input 
                type="text" 
                value={manualUrl} 
                onChange={e => setManualUrl(e.target.value)} 
                placeholder="https://youtube.com/..." 
                className="w-full px-4 py-2 border rounded-lg focus:ring-blue-500 focus:border-blue-500" 
              />
            </div>
            <div className="w-full md:w-auto">
              <label className="block text-sm font-bold text-gray-700 mb-1">Style Template</label>
              <select 
                value={manualStyle} 
                onChange={e => setManualStyle(e.target.value)} 
                className="w-full px-4 py-2 border rounded-lg focus:ring-blue-500 focus:border-blue-500 bg-white"
              >
                <option value="DEFAULT">Default (Center Crop)</option>
                <option value="GAMING_OVERLAY">Gaming Overlay</option>
                <option value="SPLIT_SCREEN">Split Screen (Satisfying)</option>
                <option value="TALKING_HEAD">Talking Head (Face Track)</option>
              </select>
            </div>
            <button 
              onClick={handleManualClip} 
              disabled={manualLoading || !manualUrl} 
              className="w-full md:w-auto bg-green-600 text-white hover:bg-green-700 disabled:bg-gray-400 px-6 py-2 rounded-lg font-bold shadow whitespace-nowrap"
            >
              {manualLoading ? "Starting..." : "Generate Clip"}
            </button>
          </div>
          
          <div className="flex border-b border-gray-200 mt-6">
            <button 
              onClick={() => setActiveTab('CRM')} 
              className={`py-2 px-6 font-bold text-lg border-b-2 transition-colors ${activeTab === 'CRM' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
            >
              CRM Outreach
            </button>
            <button 
              onClick={() => { setActiveTab('GALLERY'); fetchGallery(); }} 
              className={`py-2 px-6 font-bold text-lg border-b-2 transition-colors ${activeTab === 'GALLERY' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
            >
              Video Gallery
            </button>
          </div>
        </header>

        {activeTab === 'CRM' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {validLeads.map(lead => (
            <div key={lead.id} className={`bg-white rounded-xl shadow-sm border p-6 flex flex-col ${lead.contacted ? 'opacity-70 border-green-300' : 'border-gray-200'} ${selectedLeads.includes(lead.id) ? 'ring-2 ring-blue-400 bg-blue-50' : ''}`}>
              <div className="flex justify-between items-start mb-4">
                <div className="flex items-center space-x-3">
                  <input 
                    type="checkbox" 
                    checked={selectedLeads.includes(lead.id)}
                    onChange={() => toggleLeadSelection(lead.id)}
                    className="w-5 h-5 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                  />
                  <span className="bg-indigo-100 text-indigo-800 text-xs font-bold px-2 py-1 rounded">r/{lead.subreddit}</span>
                </div>
                {lead.contacted && <span className="bg-green-100 text-green-800 text-xs font-bold px-2 py-1 rounded">✓ Contacted</span>}
              </div>
              
              <h2 className="text-lg font-bold text-gray-900 mb-2 line-clamp-2" title={lead.title}>{lead.title}</h2>
              <a href={lead.url} target="_blank" rel="noreferrer" className="text-sm text-blue-500 hover:underline mb-4">View Original Post ↗</a>
              
              <div className="bg-gray-50 p-3 rounded text-sm text-gray-700 italic mb-4 flex-grow overflow-y-auto max-h-32">
                "{lead.proposal.substring(0, 150)}..."
              </div>
              
              {lead.video_path && (
                <div className="mb-4 bg-black rounded-lg overflow-hidden flex items-center justify-center" style={{ height: '200px' }}>
                  <video 
                    controls 
                    className="max-h-full max-w-full"
                    src={`/output_clips/${lead.video_path.split(/[\\/]/).pop()}`}
                  >
                    Your browser does not support the video tag.
                  </video>
                </div>
              )}
              
              <div className="mt-auto pt-4 border-t border-gray-100">
                {lead.contacted ? (
                  <div className="flex space-x-2">
                    <button disabled className="w-1/2 py-2 px-2 rounded-lg font-bold bg-gray-100 text-gray-400 cursor-not-allowed text-xs">
                      {lead.has_video ? "Video Uploaded" : "Contacted"}
                    </button>
                    <a href={lead.compose_url} target="_blank" rel="noreferrer" className="w-1/2 py-2 px-2 rounded-lg font-bold text-center bg-blue-100 text-blue-700 hover:bg-blue-200 transition-all text-xs">Verify / Open Reddit</a>
                  </div>
                ) : !lead.has_video ? (
                   <a 
                    href={lead.compose_url} 
                    target="_blank" 
                    rel="noreferrer"
                    className="block w-full py-3 px-4 rounded-lg font-bold transition-all text-center bg-gray-800 text-white hover:bg-gray-900 shadow-md"
                  >
                    Send Pitch (No Video) ✉️
                  </a>
                ) : (
                  <button 
                    onClick={() => handlePitch(lead.id)}
                    disabled={pitchingId === lead.id}
                    className={`w-full py-3 px-4 rounded-lg font-bold transition-all ${
                      pitchingId === lead.id 
                        ? 'bg-yellow-400 text-yellow-900 animate-pulse'
                        : 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white hover:shadow-lg hover:from-blue-700 hover:to-indigo-700 transform hover:-translate-y-1'
                    }`}
                  >
                    {pitchingId === lead.id ? 'Uploading Video...' : '1-Click Pitch 🚀'}
                  </button>
                )}
              </div>
            </div>
          ))}
          
          {validLeads.length === 0 && (
            <div className="col-span-full bg-white rounded-xl shadow p-10 text-center border border-dashed border-gray-300">
              <span className="text-4xl mb-4 block">🕵️‍♂️</span>
              <h3 className="text-xl font-bold text-gray-700">No Generated Videos Yet</h3>
              <p className="text-gray-500 mt-2">Run the scout_agent.py to find new leads and generate sample clips.</p>
            </div>
          )}
        </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
            {galleryVideos.map((vid, i) => (
               <div key={i} className="bg-white rounded-xl shadow-sm border p-4 flex flex-col">
                 <div className="mb-4 bg-black rounded-lg overflow-hidden flex items-center justify-center" style={{ height: '300px' }}>
                   <video controls className="max-h-full max-w-full" src={vid.url}>
                     Your browser does not support the video tag.
                   </video>
                 </div>
                 <h3 className="text-sm font-bold text-gray-800 break-words mb-2">{vid.filename}</h3>
                 <a href={vid.url} download className="mt-auto text-center block w-full py-2 bg-indigo-100 text-indigo-700 hover:bg-indigo-200 rounded font-bold text-sm transition-colors">
                   Download MP4
                 </a>
               </div>
            ))}
            {galleryVideos.length === 0 && (
              <div className="col-span-full py-20 text-center border-2 border-dashed border-gray-300 rounded-xl bg-white">
                <span className="text-4xl mb-4 block">🎬</span>
                <h3 className="text-xl font-bold text-gray-700">Your Gallery is Empty</h3>
                <p className="text-gray-500 mt-2">Generate some clips manually or run the scout agent!</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
