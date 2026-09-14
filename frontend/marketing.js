/**
 * Rivyn — Enterprise Product Marketing Website JavaScript
 * Handles theming, interactive ROI calculator, product tour tabs,
 * pricing toggle, FAQ accordion, and demo booking modal.
 */

(function () {
  'use strict';

  // 1. Theme Management (Synced with console app)
  const themeToggle = document.getElementById('btnThemeToggle');
  
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('rivyn-theme', theme);
    } catch (e) {
      console.warn('Storage blocked');
    }
  }

  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const current = document.documentElement.getAttribute('data-theme');
      const next = current === 'light' ? 'dark' : 'light';
      applyTheme(next);
    });
  }

  // 2. Interactive ROI & Cost Savings Calculator
  const sliderVolume = document.getElementById('sliderVolume');
  const sliderSRE = document.getElementById('sliderSRE');
  const sliderRate = document.getElementById('sliderRate');

  const valVolume = document.getElementById('valVolume');
  const valSRE = document.getElementById('valSRE');
  const valRate = document.getElementById('valRate');

  const resAnnualSavings = document.getElementById('resAnnualSavings');
  const resStorageSavings = document.getElementById('resStorageSavings');
  const resHoursSaved = document.getElementById('resHoursSaved');

  function updateCalculator() {
    if (!sliderVolume || !sliderSRE || !sliderRate) return;

    const volumeGb = parseInt(sliderVolume.value, 10);
    const sreCount = parseInt(sliderSRE.value, 10);
    const hourlyRate = parseInt(sliderRate.value, 10);

    // Update displays
    valVolume.textContent = volumeGb >= 1000 ? `${(volumeGb / 1000).toFixed(1)} TB` : `${volumeGb} GB`;
    valSRE.textContent = `${sreCount} ${sreCount === 1 ? 'Engineer' : 'Engineers'}`;
    valRate.textContent = `$${hourlyRate} / hr`;

    // Calculation Model:
    // 1. Storage: Traditional indexing / hot storage ~$0.05 / GB-month.
    //    Parquet saves 75% on average (LogHub benchmark range: 60% - 89.3%).
    const monthlyRawStorageCost = volumeGb * 30 * 0.05;
    const monthlyStorageSaved = Math.round(monthlyRawStorageCost * 0.75);

    // 2. SRE Productivity:
    //    Average engineer spends ~12 hours/week triaging alert storms, chasing false positives.
    //    Rivyn eliminates 90%+ alert noise and correlates incidents, saving ~40 hours/month per engineer.
    const monthlyHoursSaved = sreCount * 40;
    const monthlyProductivitySaved = monthlyHoursSaved * hourlyRate;

    // 3. Annual total
    const totalAnnualValue = (monthlyStorageSaved * 12) + (monthlyProductivitySaved * 12);

    // Format results
    if (resAnnualSavings) {
      resAnnualSavings.textContent = `$${totalAnnualValue.toLocaleString()}`;
    }
    if (resStorageSavings) {
      resStorageSavings.textContent = `$${monthlyStorageSaved.toLocaleString()}/mo`;
    }
    if (resHoursSaved) {
      resHoursSaved.textContent = `${monthlyHoursSaved.toLocaleString()} hrs/mo`;
    }
  }

  if (sliderVolume && sliderSRE && sliderRate) {
    sliderVolume.addEventListener('input', updateCalculator);
    sliderSRE.addEventListener('input', updateCalculator);
    sliderRate.addEventListener('input', updateCalculator);
    updateCalculator();
  }

  // 3. Interactive Product Tour Tabs
  const tourTabs = document.querySelectorAll('.tour-tab');
  const tourPanels = document.querySelectorAll('.tour-content-panel');

  tourTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const targetId = tab.getAttribute('data-tab');

      tourTabs.forEach(t => t.classList.remove('active'));
      tourPanels.forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const activePanel = document.getElementById(targetId);
      if (activePanel) {
        activePanel.classList.add('active');
      }
    });
  });

  // 4. Commercial Pricing Toggle (Monthly vs Annual)
  const pricingSwitch = document.getElementById('pricingSwitch');
  const priceProAmount = document.getElementById('priceProAmount');
  const priceProPeriod = document.getElementById('priceProPeriod');

  let isAnnual = false;
  if (pricingSwitch) {
    pricingSwitch.addEventListener('click', () => {
      isAnnual = !isAnnual;
      pricingSwitch.classList.toggle('active', isAnnual);
      
      if (priceProAmount) {
        priceProAmount.textContent = isAnnual ? '$399' : '$499';
      }
      if (priceProPeriod) {
        priceProPeriod.textContent = isAnnual ? '/ node / month (billed annually)' : '/ node / month';
      }
    });
  }

  // 5. FAQ Accordion
  const faqItems = document.querySelectorAll('.faq-item');
  faqItems.forEach(item => {
    const trigger = item.querySelector('.faq-trigger');
    if (trigger) {
      trigger.addEventListener('click', () => {
        const isOpen = item.classList.contains('open');
        faqItems.forEach(i => i.classList.remove('open'));
        if (!isOpen) {
          item.classList.add('open');
        }
      });
    }
  });

  // 6. Demo Booking Modal
  const modalBackdrop = document.getElementById('demoModal');
  const openModalBtns = document.querySelectorAll('.js-open-demo-modal');
  const closeModalBtn = document.getElementById('btnCloseDemoModal');
  const demoForm = document.getElementById('demoForm');
  const demoSuccessMsg = document.getElementById('demoSuccessMsg');

  function openModal() {
    if (modalBackdrop) {
      modalBackdrop.classList.add('open');
      document.body.style.overflow = 'hidden';
    }
  }

  function closeModal() {
    if (modalBackdrop) {
      modalBackdrop.classList.remove('open');
      document.body.style.overflow = '';
      if (demoForm) demoForm.style.display = 'block';
      if (demoSuccessMsg) demoSuccessMsg.style.display = 'none';
    }
  }

  openModalBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openModal();
    });
  });

  if (closeModalBtn) {
    closeModalBtn.addEventListener('click', closeModal);
  }

  if (modalBackdrop) {
    modalBackdrop.addEventListener('click', (e) => {
      if (e.target === modalBackdrop) {
        closeModal();
      }
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modalBackdrop && modalBackdrop.classList.contains('open')) {
      closeModal();
    }
  });

  if (demoForm) {
    demoForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const emailInput = document.getElementById('demoEmail');
      const email = emailInput ? emailInput.value : '';
      
      demoForm.style.display = 'none';
      if (demoSuccessMsg) {
        demoSuccessMsg.style.display = 'block';
        const userEmailSpan = document.getElementById('userEmailConfirm');
        if (userEmailSpan) {
          userEmailSpan.textContent = email || 'your email';
        }
      }
    });
  }

})();
