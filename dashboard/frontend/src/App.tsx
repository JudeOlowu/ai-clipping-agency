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
  compose_url?: string;
};

function App() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [pitchingId, setPitchingId] = useState<number | null>(null);
  const [selectedLeads, setSelectedLeads] = useState<number[]>([]);
  
  const [manualUrl, setManualUrl] = useState("");
  const [manualStyle, setManualStyle] = useState("DEFAULT");
  const [generateSubtitles, setGenerateSubtitles] = useState(true);
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
        if (popup) popup.location.href = data.compose_url;
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
        body: JSON.stringify({ url: manualUrl, style: manualStyle, generateSubtitles })
      });
      const data = await res.json();
      if (data.success) {
        alert("Manual clip started! The agent is rendering it in the background.");
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
        setGalleryVideos([]);
      }
    } catch (err) {
      setGalleryVideos([]);
    }
  };

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center bg-background text-white">
      <div className="flex flex-col items-center animate-fade-in-up">
        <div className="w-16 h-16 border-4 border-primary border-t-transparent rounded-full animate-spin mb-6"></div>
        <div className="text-xl font-display tracking-widest text-muted">INITIALIZING AGENCY SECURE LINK...</div>
      </div>
    </div>
  );

  const validLeads = leads;

  return (
    <div className="min-h-screen text-text p-6 md:p-10 font-sans">
      <div className="max-w-7xl mx-auto space-y-10 animate-fade-in">
        
        {/* Header Section */}
        <header className="flex flex-col md:flex-row justify-between items-start md:items-end gap-6 pb-6 border-b border-white/10">
          <div>
            <h1 className="text-5xl md:text-6xl font-display font-extrabold tracking-tight mb-2 text-gradient">
              Clipping Agency
            </h1>
            <p className="text-muted text-lg font-light tracking-wide">
              Automated client acquisition &amp; clipping pipeline.
            </p>
          </div>
          
          <div className="flex items-center gap-4">
            <button 
              onClick={handleClearLeads}
              className="px-5 py-2.5 rounded-full border border-red-500/30 text-red-400 hover:bg-red-500/10 hover:border-red-500/50 transition-all font-medium text-sm"
            >
              {selectedLeads.length > 0 ? `Delete Selected (${selectedLeads.length})` : 'Purge All Leads'}
            </button>
            <div className="px-5 py-2.5 rounded-full bg-primary/20 border border-primary/50 text-blue-300 font-semibold shadow-[0_0_15px_rgba(59,130,246,0.3)] text-sm flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
              {validLeads.length} Leads Active
            </div>
          </div>
        </header>
        
        {/* Manual Clip Action Bar */}
        <div className="glass-card p-6 flex flex-col md:flex-row gap-4 items-end animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
          <div className="flex-1 w-full pb-8 md:pb-0">
            <label className="block text-xs uppercase tracking-wider text-muted mb-2 font-semibold">Generate Manual Clip</label>
            <input 
              type="text" 
              value={manualUrl} 
              onChange={e => setManualUrl(e.target.value)} 
              placeholder="Paste YouTube or X URL here..." 
              className="w-full px-4 py-3 bg-white/5 border border-white/10 rounded-xl focus:ring-2 focus:ring-primary focus:border-transparent text-white placeholder-gray-500 transition-all outline-none" 
            />
          </div>
          <div className="w-full md:w-64 flex flex-col gap-3">
            <div>
              <label className="block text-xs uppercase tracking-wider text-muted mb-2 font-semibold">Render Template</label>
              <select 
                value={manualStyle} 
                onChange={e => setManualStyle(e.target.value)} 
                className="w-full px-4 py-3 bg-gray-900 border border-white/10 rounded-xl focus:ring-2 focus:ring-primary text-white outline-none appearance-none"
              >
                <option value="DEFAULT">Default (Center Crop)</option>
                <option value="GAMING_OVERLAY">Gaming Overlay</option>
                <option value="SPLIT_SCREEN">Split Screen (Satisfying)</option>
                <option value="TALKING_HEAD">Talking Head (Face Track)</option>
              </select>
            </div>
            <label className="flex items-center gap-2 text-sm text-gray-300 cursor-pointer">
              <input 
                type="checkbox" 
                checked={generateSubtitles} 
                onChange={e => setGenerateSubtitles(e.target.checked)} 
                className="w-4 h-4 rounded border-white/20 bg-white/5 text-primary focus:ring-primary focus:ring-offset-background cursor-pointer" 
              />
              <span className="font-medium tracking-wide">AI Subtitles</span>
            </label>
          </div>
          <button 
            onClick={handleManualClip} 
            disabled={manualLoading || !manualUrl} 
            className="w-full md:w-auto bg-gradient-to-r from-accent to-emerald-400 text-gray-900 hover:scale-105 disabled:opacity-50 disabled:hover:scale-100 px-8 py-3 rounded-xl font-bold shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:shadow-[0_0_30px_rgba(16,185,129,0.5)] transition-all whitespace-nowrap mb-[30px] md:mb-0"
          >
            {manualLoading ? "Initializing..." : "Render Clip"}
          </button>
        </div>
        
        {/* Navigation Tabs */}
        <div className="flex gap-8 border-b border-white/10 px-2">
          <button 
            onClick={() => setActiveTab('CRM')} 
            className={`pb-4 font-display text-lg tracking-wide transition-all relative ${activeTab === 'CRM' ? 'text-white' : 'text-muted hover:text-gray-300'}`}
          >
            CRM Outreach
            {activeTab === 'CRM' && <span className="absolute bottom-0 left-0 w-full h-0.5 bg-primary shadow-[0_0_10px_rgba(59,130,246,0.8)]"></span>}
          </button>
          <button 
            onClick={() => { setActiveTab('GALLERY'); fetchGallery(); }} 
            className={`pb-4 font-display text-lg tracking-wide transition-all relative ${activeTab === 'GALLERY' ? 'text-white' : 'text-muted hover:text-gray-300'}`}
          >
            Asset Gallery
            {activeTab === 'GALLERY' && <span className="absolute bottom-0 left-0 w-full h-0.5 bg-primary shadow-[0_0_10px_rgba(59,130,246,0.8)]"></span>}
          </button>
        </div>

        {/* Tab Content */}
        {activeTab === 'CRM' ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
            {validLeads.map((lead, idx) => (
              <div 
                key={lead.id} 
                className={`glass-card glass-card-hover p-6 flex flex-col ${lead.contacted ? 'opacity-60 border-accent/30' : ''} ${selectedLeads.includes(lead.id) ? 'ring-2 ring-primary/50 bg-primary/5' : ''}`}
                style={{ animationDelay: `${0.1 * (idx % 10)}s` }}
              >
                <div className="flex justify-between items-start mb-5">
                  <div className="flex items-center gap-3">
                    <input 
                      type="checkbox" 
                      checked={selectedLeads.includes(lead.id)}
                      onChange={() => toggleLeadSelection(lead.id)}
                      className="w-5 h-5 rounded border-white/20 bg-white/5 text-primary focus:ring-primary focus:ring-offset-background cursor-pointer"
                    />
                    <span className="bg-white/10 text-blue-200 text-xs font-bold px-2.5 py-1 rounded-md tracking-wider border border-white/10">
                      r/{lead.subreddit}
                    </span>
                  </div>
                  {lead.contacted && <span className="bg-accent/20 text-accent border border-accent/30 text-xs font-bold px-2.5 py-1 rounded-md flex items-center gap-1"><svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg> Deployed</span>}
                </div>
                
                <h2 className="text-xl font-display font-semibold text-white mb-2 line-clamp-2 leading-snug" title={lead.title}>{lead.title}</h2>
                <a href={lead.url} target="_blank" rel="noreferrer" className="text-sm text-primary hover:text-blue-300 hover:underline mb-5 w-max flex items-center gap-1">
                  View Target <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
                </a>
                
                <div className="bg-black/40 border border-white/5 p-4 rounded-xl text-sm text-gray-300 italic mb-5 flex-grow overflow-y-auto max-h-36 scrollbar-thin scrollbar-thumb-white/10">
                  <span className="text-primary font-serif font-bold text-lg leading-none mr-1">"</span>
                  {lead.proposal.substring(0, 180)}{lead.proposal.length > 180 ? '...' : ''}
                  <span className="text-primary font-serif font-bold text-lg leading-none ml-1">"</span>
                </div>
                
                {lead.video_path && (
                  <div className="mb-5 bg-black/80 rounded-xl overflow-hidden flex items-center justify-center border border-white/10 relative group" style={{ height: '220px' }}>
                    <video 
                      controls 
                      className="max-h-full max-w-full"
                      src={`/output_clips/${lead.video_path.split(/[\\/]/).pop()}`}
                    />
                  </div>
                )}
                
                <div className="mt-auto pt-5 border-t border-white/10">
                  {lead.contacted ? (
                    <div className="flex gap-3">
                      <button disabled className="flex-1 py-2.5 rounded-lg font-semibold bg-white/5 text-muted cursor-not-allowed text-xs border border-white/5">
                        {lead.has_video ? "Asset Delivered" : "Ping Sent"}
                      </button>
                      <a href={lead.compose_url} target="_blank" rel="noreferrer" className="flex-1 py-2.5 rounded-lg font-semibold text-center bg-primary/20 text-primary border border-primary/30 hover:bg-primary/30 transition-colors text-xs">Verify Thread</a>
                    </div>
                  ) : !lead.has_video ? (
                     <a 
                      href={lead.compose_url} 
                      target="_blank" 
                      rel="noreferrer"
                      className="flex justify-center items-center gap-2 w-full py-3.5 rounded-xl font-bold transition-all bg-white/10 text-white hover:bg-white/20 border border-white/20"
                    >
                      Deploy Text Pitch
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                    </a>
                  ) : (
                    <button 
                      onClick={() => handlePitch(lead.id)}
                      disabled={pitchingId === lead.id}
                      className={`w-full flex justify-center items-center gap-2 py-3.5 rounded-xl font-bold transition-all ${
                        pitchingId === lead.id 
                          ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/50 animate-pulse'
                          : 'bg-primary hover:bg-blue-500 text-white shadow-[0_0_20px_rgba(59,130,246,0.4)] hover:shadow-[0_0_30px_rgba(59,130,246,0.6)] hover:-translate-y-0.5'
                      }`}
                    >
                      {pitchingId === lead.id ? (
                        <>Uploading Asset...</>
                      ) : (
                        <>
                          Execute 1-Click Pitch
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            ))}
            
            {validLeads.length === 0 && (
              <div className="col-span-full glass-card p-16 text-center border border-white/5 flex flex-col items-center">
                <div className="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center mb-6 shadow-[0_0_30px_rgba(255,255,255,0.05)]">
                  <svg className="w-10 h-10 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
                </div>
                <h3 className="text-2xl font-display font-bold text-white mb-3">No Active Leads</h3>
                <p className="text-muted text-lg max-w-md mx-auto">Run the scout agent in the background to automatically populate this sector with high-value targets.</p>
              </div>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6 animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
            {galleryVideos.map((vid, i) => (
               <div key={i} className="glass-card glass-card-hover p-4 flex flex-col group">
                 <div className="mb-4 bg-black/80 rounded-xl overflow-hidden flex items-center justify-center border border-white/5 relative" style={{ height: '300px' }}>
                   <video controls className="max-h-full max-w-full" src={vid.url} />
                   <div className="absolute top-3 right-3 bg-black/60 backdrop-blur px-2 py-1 rounded text-[10px] uppercase tracking-wider text-white font-mono opacity-0 group-hover:opacity-100 transition-opacity">
                     MP4 ASSET
                   </div>
                 </div>
                 <h3 className="text-sm font-semibold text-gray-300 break-words mb-4 truncate" title={vid.filename}>{vid.filename}</h3>
                 <a href={vid.url} download className="mt-auto text-center block w-full py-2.5 bg-white/5 border border-white/10 text-white hover:bg-white/10 hover:border-white/20 rounded-lg font-bold text-sm transition-all flex items-center justify-center gap-2">
                   <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
                   Extract Asset
                 </a>
               </div>
            ))}
            {galleryVideos.length === 0 && (
              <div className="col-span-full glass-card p-16 text-center border border-white/5 flex flex-col items-center">
                <div className="w-20 h-20 bg-white/5 rounded-full flex items-center justify-center mb-6 shadow-[0_0_30px_rgba(255,255,255,0.05)]">
                  <svg className="w-10 h-10 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 4v16M17 4v16M3 8h4m10 0h4M3 12h18M3 16h4m10 0h4M4 20h16a1 1 0 001-1V5a1 1 0 00-1-1H4a1 1 0 00-1 1v14a1 1 0 001 1z" /></svg>
                </div>
                <h3 className="text-2xl font-display font-bold text-white mb-3">Asset Vault Empty</h3>
                <p className="text-muted text-lg">Generate clips manually or deploy the scout agent.</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
