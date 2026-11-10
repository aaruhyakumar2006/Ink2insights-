import React from 'react';

/**
 * Ink 2 Insight — Clinical Intake Landing Page Component
 * 
 * Props:
 * - onSignIn: Function called when any "Sign In" button is clicked
 * - onDemoLogin: Function called when 1-click Demo Login is clicked
 * - accent: Brand highlight color (defaults to #D81B60)
 */
export default function LandingPage({ onSignIn = () => {}, onDemoLogin = () => {}, accent = '#D81B60' }) {
  const handleScrollToHow = (e) => {
    e.preventDefault();
    const el = document.getElementById('how-it-works-anchor');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div style={styles.pageContainer}>
      {/* 1. Header */}
      <header style={styles.header}>
        <div style={styles.logoGroup}>
          <svg width="40" height="40" viewBox="0 0 40 40" role="img" aria-label="Ink 2 Insight logo">
            <rect width="40" height="40" rx="12" fill={accent} />
            <text x="20" y="27" textAnchor="middle" fontFamily="'Plus Jakarta Sans', sans-serif" fontWeight="800" fontSize="19" fill="#FFFFFF">
              i2
            </text>
          </svg>
          <div style={styles.brandTitle}>Ink 2 Insight</div>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <button
            type="button"
            onClick={onDemoLogin}
            style={{
              padding: '8px 14px',
              borderRadius: 8,
              border: '1px solid #F59E0B',
              background: '#FFFBEB',
              color: '#B45309',
              fontWeight: 700,
              fontSize: 13,
              cursor: 'pointer'
            }}
          >
            ⚡ Demo Login
          </button>
          <button
            type="button"
            onClick={onSignIn}
            style={{ ...styles.headerSignInBtn, color: accent, borderColor: accent }}
          >
            Sign in
          </button>
        </div>
      </header>

      {/* 2. Hero Section */}
      <section style={styles.heroSection}>
        <div style={styles.badgePill}>
          <span style={{ ...styles.badgeDot, background: accent }} />
          <span>Clinical intake for medical camps</span>
        </div>

        <h1 style={styles.heroHeadline}>
          Paper forms in.<br />
          <span style={{ color: accent }}>Verified records</span> out.
        </h1>

        <p style={styles.heroSubtext}>
          Scan a camp form with your phone. AI reads the handwriting, flags what it is unsure about, and a doctor signs off before anything is saved.
        </p>

        <div style={styles.ctaGroup}>
          <button
            type="button"
            onClick={onDemoLogin}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              padding: '14px 24px',
              borderRadius: 12,
              background: '#0F1B2D',
              color: '#FFFFFF',
              fontWeight: 700,
              fontSize: 15,
              border: 'none',
              cursor: 'pointer',
              boxShadow: '0 4px 14px rgba(15, 27, 45, 0.25)'
            }}
          >
            ⚡ Instant Demo Access (Dr. Priya)
          </button>
          <button
            type="button"
            onClick={onSignIn}
            style={{ ...styles.primaryBtn, background: accent }}
          >
            Sign in to start scanning
          </button>
          <button
            type="button"
            onClick={handleScrollToHow}
            style={styles.secondaryBtn}
          >
            See how it works
          </button>
        </div>

        {/* Scanning Document Graphic with Animated Laser */}
        <div style={styles.graphicArea}>
          <div style={styles.paperSheet}>
            <div style={{ ...styles.paperBar, width: '60%', height: 12, background: '#0F1B2D', borderRadius: 6 }} />
            <div style={{ ...styles.paperBar, width: '90%' }} />
            <div style={{ ...styles.paperBar, width: '75%' }} />
            <div style={{ ...styles.paperBar, width: '85%' }} />
            <div style={styles.paperDivider} />
            <div style={{ ...styles.paperBar, width: '70%' }} />
            <div style={{ ...styles.paperBar, width: '92%' }} />
            <div style={{ ...styles.paperBar, width: '55%' }} />
            <div style={{ ...styles.paperBar, width: '80%' }} />
            <div style={{ ...styles.laserBeam, background: accent }} />
          </div>

          {/* Floating OCR Status Badges */}
          <div style={{ ...styles.pillBadge, right: 6, top: 44, borderColor: '#CFE8D9', color: '#0E6B3D' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0E6B3D" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12.5l4.5 4.5L19 7.5" />
            </svg>
            <span>Name read</span>
          </div>

          <div style={{ ...styles.pillBadge, right: 0, top: 118, borderColor: '#CFE8D9', color: '#0E6B3D' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0E6B3D" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12.5l4.5 4.5L19 7.5" />
            </svg>
            <span>Vitals read</span>
          </div>

          <div style={{ ...styles.pillBadge, right: 14, top: 192, background: '#FFF1D6', borderColor: '#F2D49A', color: '#8A4B00' }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#8A4B00" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 3l10 18H2z" />
              <path d="M12 10v5M12 18v.5" />
            </svg>
            <span>Doctor to check</span>
          </div>
        </div>
      </section>

      {/* 3. Trust Bar */}
      <div style={styles.trustBar}>
        <div style={styles.trustItem}>Doctor-verified</div>
        <div style={styles.trustDivider} />
        <div style={styles.trustItem}>Private to your organisation</div>
        <div style={styles.trustDivider} />
        <div style={styles.trustItem}>Excel-ready</div>
      </div>

      {/* 4. How It Works Section */}
      <section id="how-it-works-anchor" style={styles.howSection}>
        <div style={styles.sectionEyebrow}>How it works</div>
        <h2 style={styles.sectionHeading}>Three steps from sheet to spreadsheet</h2>
        <div style={styles.stepsColumn}>
          <div style={styles.stepItem}>
            <div style={{ ...styles.stepNumber, background: accent }}>1</div>
            <div>
              <div style={styles.stepTitle}>Scan both pages</div>
              <p style={styles.stepDesc}>Take a photo of each page. A blur, dark or glare alert asks you to retake before the AI is used.</p>
            </div>
          </div>
          <div style={styles.stepItem}>
            <div style={{ ...styles.stepNumber, background: accent }}>2</div>
            <div>
              <div style={styles.stepTitle}>Review the flags</div>
              <p style={styles.stepDesc}>Every field shows how sure the AI was. Unclear handwriting is marked amber for a doctor to confirm.</p>
            </div>
          </div>
          <div style={styles.stepItem}>
            <div style={{ ...styles.stepNumber, background: accent }}>3</div>
            <div>
              <div style={styles.stepTitle}>Approve and export</div>
              <p style={styles.stepDesc}>A doctor approves the record, then the whole camp downloads as one Excel workbook.</p>
            </div>
          </div>
        </div>
      </section>

      {/* 5. Built for the Camp Feature Cards */}
      <section style={styles.featuresSection}>
        <div style={styles.sectionEyebrow}>Built for the camp</div>
        <h2 style={{ ...styles.sectionHeading, marginBottom: 8 }}>Everything a camp team needs</h2>

        <div style={styles.featureCard}>
          <div style={{ ...styles.featureIco, background: '#FDE3EB' }}>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#C2185B" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 8V5a1 1 0 011-1h3M16 4h3a1 1 0 011 1v3M20 16v3a1 1 0 01-1 1h-3M8 20H5a1 1 0 01-1-1v-3M4 12h16" />
            </svg>
          </div>
          <div style={styles.featureTitle}>Optical scan</div>
          <p style={styles.featureDesc}>Two-page camp forms captured from your phone camera or gallery, with a quality check on both.</p>
        </div>

        <div style={styles.featureCard}>
          <div style={{ ...styles.featureIco, background: '#E6EEFB' }}>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#1E4FA3" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 4h14v16H5z" />
              <path d="M9 9h6M9 13h6M9 17h3" />
            </svg>
          </div>
          <div style={styles.featureTitle}>AI extraction</div>
          <p style={styles.featureDesc}>Reads 95+ clinical fields and vitals into structured data, with a confidence level on every field.</p>
        </div>

        <div style={styles.featureCard}>
          <div style={{ ...styles.featureIco, background: '#FFF1D6' }}>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#8A4B00" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 3l10 18H2z" />
              <path d="M12 10v5M12 18v.5" />
            </svg>
          </div>
          <div style={styles.featureTitle}>Doctor triage</div>
          <p style={styles.featureDesc}>Amber flags for low-confidence handwriting. Nothing is approved until a physician signs off.</p>
        </div>

        <div style={styles.featureCard}>
          <div style={{ ...styles.featureIco, background: '#E3F4EA' }}>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#0E6B3D" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="16" rx="2" />
              <path d="M3 10h18M9 4v16" />
            </svg>
          </div>
          <div style={styles.featureTitle}>Excel workbook</div>
          <p style={styles.featureDesc}>One workbook per camp, ready for your reports and analysis.</p>
        </div>
      </section>

      {/* 6. Roles View Section */}
      <section style={styles.rolesSection}>
        <h2 style={styles.sectionHeading}>The right view for every role</h2>
        <div style={styles.rolesColumn}>
          <div style={styles.roleCard}>
            <div style={styles.roleName}>Field worker</div>
            <p style={styles.roleDesc}>A scan-first home screen. Capture forms and fix identity details.</p>
          </div>
          <div style={styles.roleCard}>
            <div style={styles.roleName}>Doctor</div>
            <p style={styles.roleDesc}>Review flagged fields, edit clinical details and approve records.</p>
          </div>
          <div style={styles.roleCard}>
            <div style={styles.roleName}>Admin</div>
            <p style={styles.roleDesc}>Manage your team, usage and exports for the whole camp.</p>
          </div>
        </div>
      </section>

      {/* 7. Bottom CTA Banner */}
      <section style={styles.ctaBanner}>
        <h2 style={{ ...styles.sectionHeading, color: '#FFFFFF' }}>Ready for your next camp?</h2>
        <p style={styles.ctaBannerText}>Sign in to scan forms, review records and export your camp data.</p>
        <button
          type="button"
          onClick={onSignIn}
          style={{ ...styles.ctaBannerBtn, background: accent }}
        >
          Sign in
        </button>
      </section>

      {/* 8. Footer */}
      <footer style={styles.footer}>
        <div style={styles.footerBrand}>Ink 2 Insight</div>
        <div style={styles.footerTagline}>Ideas to Impact · Clinical Intake</div>
        <div style={styles.footerCopyright}>© 2026 Ink 2 Insight</div>
      </footer>

      {/* Embedded CSS for smooth keyframes */}
      <style>{`
        @keyframes scanLaser {
          0% { top: 35px; opacity: 0.85; }
          50% { opacity: 1; }
          100% { top: 255px; opacity: 0.85; }
        }
      `}</style>
    </div>
  );
}

const styles = {
  pageContainer: {
    width: '100%',
    maxWidth: 480,
    margin: '0 auto',
    background: '#FFFFFF',
    fontFamily: "'Plus Jakarta Sans', system-ui, -apple-system, sans-serif",
    color: '#0F1B2D',
    overflowX: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '14px 20px',
    background: '#FFFFFF',
    position: 'sticky',
    top: 0,
    zIndex: 20,
    borderBottom: '1px solid #F5E5EC',
  },
  logoGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  brandTitle: {
    fontWeight: 800,
    fontSize: 18,
    letterSpacing: '-0.01em',
    color: '#0F1B2D',
  },
  headerSignInBtn: {
    minHeight: 44,
    fontSize: 15,
    fontWeight: 700,
    padding: '0 18px',
    borderRadius: 16,
    border: '2px solid',
    background: 'transparent',
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  heroSection: {
    background: '#FFF4F7',
    padding: '36px 20px 40px',
    display: 'flex',
    flexDirection: 'column',
    gap: 22,
  },
  badgePill: {
    alignSelf: 'flex-start',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    background: '#FFFFFF',
    border: '1px solid #F3D3DE',
    borderRadius: 999,
    padding: '8px 14px',
    fontSize: 13,
    fontWeight: 700,
    color: '#A3123F',
  },
  badgeDot: {
    width: 8,
    height: 8,
    borderRadius: '50%',
  },
  heroHeadline: {
    margin: 0,
    fontSize: 40,
    lineHeight: 1.05,
    letterSpacing: '-0.03em',
    fontWeight: 800,
    color: '#0F1B2D',
  },
  heroSubtext: {
    margin: 0,
    fontSize: 16.5,
    lineHeight: 1.55,
    color: '#4A5568',
  },
  ctaGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  primaryBtn: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 52,
    borderRadius: 16,
    fontWeight: 700,
    fontSize: 16,
    padding: '0 22px',
    color: '#FFFFFF',
    border: 'none',
    boxShadow: '0 10px 24px rgba(216, 27, 96, 0.28)',
    cursor: 'pointer',
  },
  secondaryBtn: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 52,
    borderRadius: 16,
    fontWeight: 700,
    fontSize: 16,
    padding: '0 22px',
    background: '#FFFFFF',
    color: '#0F1B2D',
    border: '1px solid #E5C3D0',
    cursor: 'pointer',
  },
  graphicArea: {
    position: 'relative',
    height: 330,
    marginTop: 8,
  },
  paperSheet: {
    position: 'absolute',
    left: 36,
    top: 6,
    width: 230,
    height: 310,
    background: '#FFFFFF',
    border: '1px solid #EBCBD6',
    borderRadius: 20,
    transform: 'rotate(-4deg)',
    boxShadow: '0 24px 48px rgba(15, 27, 45, 0.12)',
    padding: 20,
    boxSizing: 'border-box',
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
    overflow: 'hidden',
  },
  paperBar: {
    height: 8,
    background: '#E8DDE2',
    borderRadius: 4,
  },
  paperDivider: {
    height: 1,
    background: '#F0E3E8',
    margin: '4px 0',
  },
  laserBeam: {
    position: 'absolute',
    left: -10,
    right: -10,
    top: 140,
    height: 3,
    borderRadius: 2,
    boxShadow: '0 0 18px 4px rgba(216, 27, 96, 0.5)',
    animation: 'scanLaser 2.4s ease-in-out infinite alternate',
  },
  pillBadge: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    background: '#FFFFFF',
    borderRadius: 14,
    padding: '10px 14px',
    fontSize: 14,
    fontWeight: 700,
    boxShadow: '0 10px 24px rgba(15, 27, 45, 0.10)',
    position: 'absolute',
    border: '1px solid',
  },
  trustBar: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
    padding: '22px 20px',
    background: '#0F1B2D',
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: 600,
    textAlign: 'center',
  },
  trustItem: {
    flex: 1,
  },
  trustDivider: {
    width: 1,
    height: 24,
    background: '#32425A',
  },
  howSection: {
    padding: '48px 20px 24px',
    display: 'flex',
    flexDirection: 'column',
    gap: 22,
    background: '#FFFFFF',
  },
  sectionEyebrow: {
    fontSize: 13,
    fontWeight: 800,
    letterSpacing: '0.12em',
    textTransform: 'uppercase',
    color: '#A3123F',
  },
  sectionHeading: {
    margin: 0,
    fontSize: 28,
    lineHeight: 1.15,
    letterSpacing: '-0.02em',
    fontWeight: 800,
    color: '#0F1B2D',
  },
  stepsColumn: {
    display: 'flex',
    flexDirection: 'column',
    gap: 18,
  },
  stepItem: {
    display: 'flex',
    gap: 16,
    alignItems: 'flex-start',
  },
  stepNumber: {
    flex: 'none',
    width: 44,
    height: 44,
    borderRadius: '50%',
    color: '#FFFFFF',
    fontWeight: 800,
    fontSize: 18,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepTitle: {
    fontWeight: 800,
    fontSize: 18,
    color: '#0F1B2D',
  },
  stepDesc: {
    color: '#4A5568',
    lineHeight: 1.5,
    marginTop: 4,
    fontSize: 14.5,
  },
  featuresSection: {
    padding: '24px 20px 24px',
    display: 'flex',
    flexDirection: 'column',
    gap: 14,
    background: '#FFFFFF',
  },
  featureCard: {
    background: '#FFFFFF',
    border: '1px solid #F3D3DE',
    borderRadius: 24,
    padding: 22,
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
    boxShadow: '0 4px 12px rgba(15, 27, 45, 0.03)',
  },
  featureIco: {
    width: 48,
    height: 48,
    borderRadius: 14,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  featureTitle: {
    fontWeight: 800,
    fontSize: 19,
    color: '#0F1B2D',
  },
  featureDesc: {
    color: '#4A5568',
    lineHeight: 1.5,
    margin: 0,
    fontSize: 14,
  },
  rolesSection: {
    padding: '32px 20px 48px',
    background: '#FFF4F7',
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
  },
  rolesColumn: {
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  roleCard: {
    background: '#FFFFFF',
    borderRadius: 20,
    padding: '18px 20px',
    border: '1px solid #F3D3DE',
  },
  roleName: {
    fontWeight: 800,
    fontSize: 17,
    color: '#0F1B2D',
  },
  roleDesc: {
    color: '#4A5568',
    lineHeight: 1.5,
    marginTop: 4,
    marginBottom: 0,
    fontSize: 14,
  },
  ctaBanner: {
    background: '#0F1B2D',
    color: '#FFFFFF',
    padding: '48px 20px',
    display: 'flex',
    flexDirection: 'column',
    gap: 18,
    textAlign: 'center',
    alignItems: 'center',
  },
  ctaBannerText: {
    color: '#C9D3E3',
    lineHeight: 1.55,
    fontSize: 16,
    margin: 0,
  },
  ctaBannerBtn: {
    width: '100%',
    boxSizing: 'border-box',
    color: '#FFFFFF',
    minHeight: 52,
    borderRadius: 16,
    fontWeight: 700,
    fontSize: 16,
    border: 'none',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    boxShadow: '0 8px 20px rgba(216, 27, 96, 0.35)',
  },
  footer: {
    padding: '22px 20px 28px',
    background: '#0B1422',
    color: '#9AA7BC',
    fontSize: 13,
    textAlign: 'center',
    lineHeight: 1.6,
  },
  footerBrand: {
    color: '#FFFFFF',
    fontWeight: 800,
    fontSize: 15,
  },
  footerTagline: {
    color: '#9AA7BC',
    fontSize: 12,
  },
  footerCopyright: {
    marginTop: 6,
    color: '#64748B',
    fontSize: 11.5,
  },
};
