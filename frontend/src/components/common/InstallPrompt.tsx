import { useState, useEffect } from 'react';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

// Global ref so Topbar can also trigger install
declare global {
  interface Window {
    __pwaInstallPrompt?: BeforeInstallPromptEvent | null;
    __pwaInstallFn?: () => void;
  }
}

export function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [showBanner, setShowBanner] = useState(false);
  const [isIOS, setIsIOS] = useState(false);
  const [showIOSGuide, setShowIOSGuide] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);

  useEffect(() => {
    // Check if already installed as standalone
    if (window.matchMedia('(display-mode: standalone)').matches) {
      setIsInstalled(true);
      return;
    }
    // @ts-ignore
    if (window.navigator.standalone === true) {
      setIsInstalled(true);
      return;
    }

    // iOS detection
    const ua = navigator.userAgent;
    const isiOS = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    setIsIOS(isiOS);

    if (isiOS) {
      // On iOS, show banner after 3 seconds (no beforeinstallprompt support)
      const dismissed = localStorage.getItem('pwa-install-dismissed');
      if (dismissed && Date.now() - parseInt(dismissed) < 3 * 24 * 60 * 60 * 1000) return;
      setTimeout(() => setShowBanner(true), 3000);
      return;
    }

    // Android/Chrome - listen for beforeinstallprompt
    const handler = (e: Event) => {
      e.preventDefault();
      const prompt = e as BeforeInstallPromptEvent;
      setDeferredPrompt(prompt);
      window.__pwaInstallPrompt = prompt;

      // Check if dismissed recently (only 1 day now, not 7)
      const dismissed = localStorage.getItem('pwa-install-dismissed');
      if (dismissed && Date.now() - parseInt(dismissed) < 24 * 60 * 60 * 1000) return;

      setTimeout(() => setShowBanner(true), 2000);
    };
    window.addEventListener('beforeinstallprompt', handler);

    // Also listen for successful install
    window.addEventListener('appinstalled', () => {
      setIsInstalled(true);
      setShowBanner(false);
      window.__pwaInstallPrompt = null;
    });

    // Expose install function globally for Topbar menu
    window.__pwaInstallFn = () => {
      if (window.__pwaInstallPrompt) {
        window.__pwaInstallPrompt.prompt();
      } else if (isiOS) {
        setShowIOSGuide(true);
        setShowBanner(true);
      }
    };

    return () => window.removeEventListener('beforeinstallprompt', handler);
  }, []);

  const handleInstall = async () => {
    if (isIOS) {
      setShowIOSGuide(true);
      return;
    }
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') {
      setShowBanner(false);
      setIsInstalled(true);
    }
    setDeferredPrompt(null);
    window.__pwaInstallPrompt = null;
  };

  const handleDismiss = () => {
    setShowBanner(false);
    setShowIOSGuide(false);
    localStorage.setItem('pwa-install-dismissed', Date.now().toString());
  };

  if (isInstalled || !showBanner) return null;

  // iOS instruction guide
  if (showIOSGuide) {
    return (
      <div className="fixed bottom-0 left-0 right-0 z-[200] bg-white border-t-2 border-[#0078d4] shadow-[0_-4px_20px_rgba(0,0,0,0.15)] p-4 animate-slideUp safe-bottom">
        <div className="max-w-md mx-auto">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-[15px] font-semibold text-[#323130]">Instalar Maquita Mail</h3>
            <button onClick={handleDismiss} className="text-[#605e5c] hover:text-[#323130] text-xl leading-none">&times;</button>
          </div>
          <div className="space-y-3 text-[13px] text-[#323130]">
            <div className="flex items-start gap-3">
              <span className="bg-[#0078d4] text-white w-6 h-6 rounded-full flex items-center justify-center text-[12px] font-bold shrink-0">1</span>
              <span>Toca el bot&oacute;n <strong>Compartir</strong> en la barra del navegador</span>
            </div>
            <div className="flex items-start gap-3">
              <span className="bg-[#0078d4] text-white w-6 h-6 rounded-full flex items-center justify-center text-[12px] font-bold shrink-0">2</span>
              <span>Selecciona <strong>"Agregar a pantalla de inicio"</strong></span>
            </div>
            <div className="flex items-start gap-3">
              <span className="bg-[#0078d4] text-white w-6 h-6 rounded-full flex items-center justify-center text-[12px] font-bold shrink-0">3</span>
              <span>Toca <strong>"Agregar"</strong> para confirmar</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Install banner
  return (
    <div className="fixed bottom-0 left-0 right-0 z-[200] bg-white border-t-2 border-[#0078d4] shadow-[0_-4px_20px_rgba(0,0,0,0.15)] px-4 py-3 animate-slideUp safe-bottom">
      <div className="max-w-md mx-auto flex items-center gap-3">
        <img src="/webmail/icons/icon-192.png" alt="Maquita Mail" className="w-10 h-10 rounded-xl shadow" />
        <div className="flex-1 min-w-0">
          <div className="text-[14px] font-semibold text-[#323130]">Maquita Mail</div>
          <div className="text-[12px] text-[#605e5c]">Instalar como aplicaci&oacute;n</div>
        </div>
        <button
          onClick={handleInstall}
          className="bg-[#0078d4] text-white px-4 py-2 rounded-md text-[13px] font-semibold hover:bg-[#106ebe] transition-colors shrink-0"
        >
          Instalar
        </button>
        <button onClick={handleDismiss} className="text-[#605e5c] hover:text-[#323130] text-lg leading-none shrink-0 ml-1">&times;</button>
      </div>
    </div>
  );
}
