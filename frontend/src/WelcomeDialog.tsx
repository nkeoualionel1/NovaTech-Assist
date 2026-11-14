import { useEffect, useRef, useState } from "react";

const HIDE_WELCOME_KEY = "novatech-assist:hide-welcome";

const FEATURES = [
  { icon: "", text: "Livraison, retours, garantie et paiement" },
  { icon: "", text: "Conseils produits et compatibilité des composants" },
  { icon: "", text: "Disponibilité des produits en temps réel" },
  { icon: "", text: "Suivi de commande (numéro CMD-XXXXX et e-mail d'achat)" },
  { icon: "", text: "Aide au dépannage de votre matériel" },
  { icon: "", text: "Transfert vers un conseiller si besoin" },
];

/** Vrai si le visiteur a demandé à ne plus voir la fenêtre d'accueil. */
export function isWelcomeHidden(): boolean {
  try {
    return localStorage.getItem(HIDE_WELCOME_KEY) === "1";
  } catch {
    return false; // stockage indisponible (navigation privée…) : on affiche la fenêtre
  }
}

/** Fenêtre d'accueil qui présente l'assistant ; la fermer donne accès à la conversation. */
export function WelcomeDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const startButtonRef = useRef<HTMLButtonElement>(null);
  const [hideNextTime, setHideNextTime] = useState(isWelcomeHidden);

  // <dialog> natif : piège le focus, ferme avec Échap et rend le reste de la page inactif.
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
      // Focus sur « Commencer » sans faire défiler : sur mobile, le titre reste visible.
      startButtonRef.current?.focus({ preventScroll: true });
      dialog.scrollTop = 0;
    }
    if (!open && dialog.open) dialog.close();
  }, [open]);

  function rememberChoice(hide: boolean) {
    setHideNextTime(hide);
    try {
      if (hide) localStorage.setItem(HIDE_WELCOME_KEY, "1");
      else localStorage.removeItem(HIDE_WELCOME_KEY);
    } catch {
      // stockage indisponible : le choix ne sera simplement pas mémorisé
    }
  }

  return (
    <dialog
      ref={dialogRef}
      className="welcome-dialog"
      aria-labelledby="welcome-title"
      onClose={onClose}
      onClick={(e) => e.target === dialogRef.current && dialogRef.current?.close()}
    >
      <div className="welcome-dialog-body">
        <div className="welcome-dialog-header">
          <span className="logo" aria-hidden="true">N</span>
          <h2 id="welcome-title">Bienvenue sur NovaTech Assist</h2>
        </div>

        <p className="welcome-dialog-intro">
          L'assistant virtuel du service client de NovaTech Informatique. Il répond à vos questions
          en s'appuyant uniquement sur notre documentation et notre catalogue.
        </p>

        <h3>Ce qu'il peut faire pour vous</h3>
        <ul className="feature-list">
          {FEATURES.map((f) => (
            <li key={f.text}>
              <span aria-hidden="true">{f.icon}</span>
              {f.text}
            </li>
          ))}
        </ul>

        <h3>Bon à savoir</h3>
        <ul className="tips">
          <li>Chaque réponse indique ses sources : cliquez dessus pour lire le document d'origine.</li>
          <li>
            <strong>Ne communiquez jamais</strong> vos coordonnées bancaires ni vos mots de passe
            dans la conversation.
          </li>
          <li>Projet de démonstration : l'entreprise, les clients et les commandes sont fictifs.</li>
        </ul>

        <div className="welcome-dialog-footer">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={hideNextTime}
              onChange={(e) => rememberChoice(e.target.checked)}
            />
            Ne plus afficher au démarrage
          </label>
          <button ref={startButtonRef} className="button-primary" onClick={() => dialogRef.current?.close()}>
            Commencer la conversation
          </button>
        </div>
      </div>
    </dialog>
  );
}
