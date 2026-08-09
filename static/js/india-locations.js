/**
 * CamCrew Studio — Comprehensive Indian Location Data & Cascading Dropdown System
 * Hierarchy: State / UT -> District -> City / Town
 */

const INDIA_LOCATIONS = {
  "Andhra Pradesh": {
    "Visakhapatnam": ["Visakhapatnam", "Anakapalle", "Bheemunipatnam", "Gajuwaka"],
    "NTR / Vijayawada": ["Vijayawada", "Nandigama", "Jaggayyapeta", "Tiruvuru"],
    "Guntur": ["Guntur", "Tenali", "Mangalagiri", "Ponnur"],
    "Tirupati": ["Tirupati", "Srikalahasti", "Puttur", "Gudur"],
    "Kakinada": ["Kakinada", "Pithapuram", "Samalkot", "Tuni"],
    "Kurnool": ["Kurnool", "Adoni", "Yemmiganur", "Dhone"],
    "Ananthapuramu": ["Anantapur", "Dharmavaram", "Guntakal", "Tadipatri"],
    "YSR Kadapa": ["Kadapa", "Proddatur", "Pulivendula", "Jammalamadugu"],
    "East Godavari": ["Rajamahendravaram", "Amalapuram", "Kothapeta"],
    "Eluru": ["Eluru", "Jangareddigudem", "Nuzvid"]
  },
  "Arunachal Pradesh": {
    "Papum Pare": ["Itanagar", "Naharlagun", "Yupia"],
    "Tawang": ["Tawang", "Lumbding"],
    "West Kameng": ["Bomdila", "Dirang"],
    "East Siang": ["Pasighat"],
    "Lower Subansiri": ["Ziro"]
  },
  "Assam": {
    "Kamrup Metropolitan": ["Guwahati", "Dispur"],
    "Cachar": ["Silchar", "Lakhipur"],
    "Dibrugarh": ["Dibrugarh", "Chabua", "Naharkatia"],
    "Jorhat": ["Jorhat", "Titabor", "Mariani"],
    "Nagaon": ["Nagaon", "Raha", "Hojai"],
    "Tinsukia": ["Tinsukia", "Digboi", "Margherita"],
    "Sonitpur": ["Tezpur", "Dhekiajuli"]
  },
  "Bihar": {
    "Patna": ["Patna", "Danapur", "Phulwari Sharif", "Fatwah"],
    "Gaya": ["Gaya", "Bodhgaya", "Sherghati"],
    "Bhagalpur": ["Bhagalpur", "Kahalgaon", "Naugachhia"],
    "Muzaffarpur": ["Muzaffarpur", "Kanti", "Motipur"],
    "Purnia": ["Purnia", "Kasba", "Banmankhi"],
    "Darbhanga": ["Darbhanga", "Benipur"],
    "Begusarai": ["Begusarai", "Barauni"]
  },
  "Chhattisgarh": {
    "Raipur": ["Raipur", "Abhanpur", "Tilda"],
    "Durg": ["Bhilai", "Durg", "Patan"],
    "Bilaspur": ["Bilaspur", "Kota", "Takhatpur"],
    "Korba": ["Korba", "Katghora"],
    "Rajnandgaon": ["Rajnandgaon", "Dongargarh"]
  },
  "Delhi (NCR)": {
    "New Delhi": ["Connaught Place", "Chanakyapuri", "Vasant Kunj"],
    "South Delhi": ["Saket", "Hauz Khas", "Greater Kailash", "Lajpat Nagar"],
    "North Delhi": ["Civil Lines", "Model Town", "Pitampura"],
    "East Delhi": ["Mayur Vihar", "Preet Vihar", "Laxmi Nagar"],
    "West Delhi": ["Rajouri Garden", "Janakpuri", "Dwarka"],
    "Gurugram (NCR)": ["DLF Cyber City", "Golf Course Road", "Sohna Road", "Sector 56"],
    "Noida (NCR)": ["Sector 18", "Sector 62", "Greater Noida", "Noida Extension"],
    "Faridabad (NCR)": ["Sector 15", "NIT Faridabad", "Ballabgarh"],
    "Ghaziabad (NCR)": ["Indirapuram", "Vaishali", "Raj Nagar Extension"]
  },
  "Goa": {
    "North Goa": ["Panaji", "Mapusa", "Calangute", "Candolim", "Anjuna", "Bicholim"],
    "South Goa": ["Margao", "Vasco da Gama", "Ponda", "Curchorem", "Palolem"]
  },
  "Gujarat": {
    "Ahmedabad": ["Ahmedabad", "Bodakdev", "Satellite", "SG Highway", "Maninagar", "Sanand"],
    "Surat": ["Surat", "Adajan", "Vesu", "Varachha", "Katargam"],
    "Vadodara": ["Vadodara", "Alkapuri", "Gotri", "Sayajigunj", "Manjalpur"],
    "Rajkot": ["Rajkot", "Kalawad Road", "University Road", "Morbi Road"],
    "Bhavnagar": ["Bhavnagar", "Palitana"],
    "Jamnagar": ["Jamnagar", "Dwarka"],
    "Gandhinagar": ["Gandhinagar", "GIFT City", "Kudasan"]
  },
  "Haryana": {
    "Gurugram": ["Gurugram", "Manesar", "Sohna"],
    "Faridabad": ["Faridabad", "Ballabgarh"],
    "Panipat": ["Panipat", "Samalkha"],
    "Ambala": ["Ambala Cantt", "Ambala City"],
    "Panchkula": ["Panchkula", "Kalka"],
    "Karnal": ["Karnal", "Gharaunda"],
    "Hisar": ["Hisar", "Hansi"]
  },
  "Himachal Pradesh": {
    "Shimla": ["Shimla", "Kufri", "Mashobra"],
    "Kangra": ["Dharamshala", "Palampur", "Kangra", "McLeod Ganj"],
    "Kullu": ["Kullu", "Manali", "Kasol", "Bhuntar"],
    "Solan": ["Solan", "Baddi", "Kasauli"],
    "Mandi": ["Mandi", "Sundernagar"]
  },
  "Jammu & Kashmir": {
    "Srinagar": ["Srinagar", "Hazratbal", "Lal Chowk"],
    "Jammu": ["Jammu", "Gandhi Nagar", "Trikuta Nagar"],
    "Anantnag": ["Anantnag", "Pahalgam"],
    "Baramulla": ["Baramulla", "Gulmarg"]
  },
  "Jharkhand": {
    "Ranchi": ["Ranchi", "Dhurwa", "Kanke", "Bariatu"],
    "East Singhbhum": ["Jamshedpur", "Bistupur", "Sakchi", "Kadma"],
    "Dhanbad": ["Dhanbad", "Jharia", "Katras"],
    "Bokaro": ["Bokaro Steel City", "Chas"],
    "Hazaribagh": ["Hazaribagh"]
  },
  "Karnataka": {
    "Bengaluru Urban": ["Indiranagar", "Koramangala", "HSR Layout", "Jayanagar", "Whitefield", "Electronic City", "MG Road", "Hebbal", "Yelahanka", "Marathahalli"],
    "Mysuru": ["Mysuru", "Gokulam", "Vijayanagar", "Jayalakshmipuram"],
    "Dakshina Kannada": ["Mangaluru", "Surathkal", "Bantwal"],
    "Dharwad": ["Hubballi", "Dharwad"],
    "Belagavi": ["Belagavi", "Gokak"],
    "Udupi": ["Udupi", "Manipal", "Kundapura"],
    "Shivamogga": ["Shivamogga", "Bhadravathi"],
    "Davanagere": ["Davanagere", "Harihar"],
    "Tumakuru": ["Tumakuru", "Tiptur"]
  },
  "Kerala": {
    "Ernakulam": ["Kochi", "Fort Kochi", "Edappally", "Kakkanad", "Aluva", "Tripunithura", "Perumbavoor", "Muvattupuzha"],
    "Thiruvananthapuram": ["Thiruvananthapuram", "Technopark", "Kazhakkoottam", "Varkala", "Kovalam", "Neyyattinkara"],
    "Kozhikode": ["Kozhikode", "Vadakara", "Koyilandy", "Ramanattukara"],
    "Thrissur": ["Thrissur", "Guruvayur", "Irinjalakuda", "Chalakudy", "Kunnamkulam"],
    "Kollam": ["Kollam", "Karunagappally", "Punalur", "Kottarakkara"],
    "Kannur": ["Kannur", "Thalassery", "Payyanur", "Mattannur"],
    "Kottayam": ["Kottayam", "Changanassery", "Pala", "Kanjirappally"],
    "Alappuzha": ["Alappuzha", "Cherthala", "Kayamkulam", "Chengannur"],
    "Palakkad": ["Palakkad", "Ottapalam", "Chittur"],
    "Malappuram": ["Malappuram", "Manjeri", "Perinthalmanna", "Tirur"],
    "Kasaragod": ["Kasaragod", "Kanhangad"],
    "Pathanamthitta": ["Pathanamthitta", "Tiruvalla", "Adoor"],
    "Idukki": ["Munnar", "Thodupuzha", "Kattappana"],
    "Wayanad": ["Kalpetta", "Sulthan Bathery", "Mananthavady"]
  },
  "Madhya Pradesh": {
    "Bhopal": ["Bhopal", "Arera Colony", "MP Nagar", "Kolar"],
    "Indore": ["Indore", "Vijay Nagar", "Palasia", "Bhawarkua", "Rau"],
    "Jabalpur": ["Jabalpur", "Civil Lines", "Wright Town"],
    "Gwalior": ["Gwalior", "City Center", "Lashkar"],
    "Ujjain": ["Ujjain", "Freeganj"]
  },
  "Maharashtra": {
    "Mumbai City & Suburban": ["South Mumbai", "Bandra", "Andheri", "Juhu", "Powai", "Worli", "Lower Parel", "Borivali", "Goregaon", "Malad", "Dadar", "Chembur", "Kurla"],
    "Thane": ["Thane", "Navi Mumbai (Vashi, Nerul, Belapur)", "Kalyan", "Dombivli", "Mira-Bhayandar"],
    "Pune": ["Koregaon Park", "Baner", "Viman Nagar", "Kothrud", "Wakad", "Hinjawadi", "Pimpri-Chinchwad", "Shivajinagar"],
    "Nagpur": ["Nagpur", "Dharampeth", "Civil Lines", "Sadar"],
    "Nashik": ["Nashik", "College Road", "Gangapur Road", "Indira Nagar"],
    "Chhatrapati Sambhajinagar (Aurangabad)": ["Chhatrapati Sambhajinagar", "Cidco", "Nirala Bazar"],
    "Kolhapur": ["Kolhapur", "Rajarampuri", "Tarabai Park"],
    "Solapur": ["Solapur"],
    "Satara": ["Satara", "Mahabaleshwar", "Panchgani"]
  },
  "Manipur": {
    "Imphal West": ["Imphal", "Lamsang"],
    "Imphal East": ["Porompat", "Lamlai"],
    "Churachandpur": ["Churachandpur"]
  },
  "Meghalaya": {
    "East Khasi Hills": ["Shillong", "Laitumkhrah", "Cherrapunji (Sohra)"],
    "West Garo Hills": ["Tura"],
    "Ri-Bhoi": ["Nongpoh"]
  },
  "Mizoram": {
    "Aizawl": ["Aizawl", "Bawngkawn"],
    "Lunglei": ["Lunglei"]
  },
  "Nagaland": {
    "Kohima": ["Kohima"],
    "Dimapur": ["Dimapur", "Chümoukedima"]
  },
  "Odisha": {
    "Khurda": ["Bhubaneswar", "Jatani"],
    "Cuttack": ["Cuttack", "Choudwar"],
    "Ganjam": ["Berhampur", "Chhatrapur"],
    "Sundargarh": ["Rourkela"],
    "Puri": ["Puri", "Konark"],
    "Sambalpur": ["Sambalpur", "Burla"]
  },
  "Punjab": {
    "Ludhiana": ["Ludhiana", "Model Town", "Civil Lines", "Sarabha Nagar"],
    "Amritsar": ["Amritsar", "Ranjit Avenue", "Mall Road"],
    "Jalandhar": ["Jalandhar", "Model Town", "BMC Chowk"],
    "Patiala": ["Patiala", "Urban Estate"],
    "SAS Nagar (Mohali)": ["Mohali", "Sector 70", "Sector 82"],
    "Bathinda": ["Bathinda"]
  },
  "Rajasthan": {
    "Jaipur": ["Jaipur", "C-Scheme", "Malviya Nagar", "Vaishali Nagar", "Raja Park", "Mansarovar"],
    "Jodhpur": ["Jodhpur", "Ratanada", "Shastri Nagar"],
    "Udaipur": ["Udaipur", "Fatehpura", "Hiran Magri", "Old City"],
    "Kota": ["Kota", "Talwandi", "Vigyan Nagar"],
    "Ajmer": ["Ajmer", "Pushkar"],
    "Bikaner": ["Bikaner"]
  },
  "Sikkim": {
    "East Sikkim": ["Gangtok", "Rangpo", "Singtam"],
    "South Sikkim": ["Namchi"]
  },
  "Tamil Nadu": {
    "Chennai": ["Nungambakkam", "T. Nagar", "Adyar", "Mylapore", "Velachery", "Anna Nagar", "O M R (IT Corridor)", "ECR"],
    "Coimbatore": ["Coimbatore", "RS Puram", "Peelamedu", "Gandhipuram", "Race Course"],
    "Madurai": ["Madurai", "Anna Nagar", "KK Nagar"],
    "Tiruchirappalli": ["Tiruchirappalli", "Thillai Nagar", "Srirangam"],
    "Salem": ["Salem", "Fairlands"],
    "Tiruppur": ["Tiruppur"],
    "Nilgiris": ["Udhagamandalam (Ooty)", "Coonoor"]
  },
  "Telangana": {
    "Hyderabad / Rangareddy": ["Banjara Hills", "Jubilee Hills", "HITEC City", "Gachibowli", "Madhapur", "Kondapur", "Secunderabad", "Begumpet", "Kukatpally"],
    "Warangal": ["Warangal", "Hanamkonda", "Kazipet"],
    "Nizamabad": ["Nizamabad"],
    "Karimnagar": ["Karimnagar"],
    "Khammam": ["Khammam"]
  },
  "Tripura": {
    "West Tripura": ["Agartala"],
    "Gomati": ["Udaipur"]
  },
  "Uttar Pradesh": {
    "Lucknow": ["Lucknow", "Hazratganj", "Gomti Nagar", "Aliganj", "Indira Nagar"],
    "Gautam Buddha Nagar (Noida)": ["Noida", "Greater Noida", "Noida Extension"],
    "Ghaziabad": ["Ghaziabad", "Indirapuram", "Vaishali", "Raj Nagar"],
    "Kanpur": ["Kanpur", "Civil Lines", "Swaroop Nagar"],
    "Varanasi": ["Varanasi", "Lanka", "Cantonment", "Assi Ghat"],
    "Agra": ["Agra", "Tajganj", "Sanjay Place"],
    "Prayagraj (Allahabad)": ["Prayagraj", "Civil Lines"],
    "Meerut": ["Meerut"],
    "Gorakhpur": ["Gorakhpur"]
  },
  "Uttarakhand": {
    "Dehradun": ["Dehradun", "Rishikesh", "Mussoorie", "Rajpur Road"],
    "Haridwar": ["Haridwar", "Roorkee"],
    "Nainital": ["Nainital", "Haldwani", "Bhowali"],
    "Udham Singh Nagar": ["Rudrapur", "Kashipur"]
  },
  "West Bengal": {
    "Kolkata": ["Park Street", "Salt Lake", "New Town", "Ballygunge", "Alipore", "Tollygunge", "Howrah"],
    "Darjeeling": ["Darjeeling", "Siliguri", "Kalimpong"],
    "Paschim Bardhaman": ["Asansol", "Durgapur"],
    "East Midnapore": ["Haldia", "Digha"]
  }
};

/**
 * Returns array of all Indian State/UT names
 */
function getIndianStates() {
  return Object.keys(INDIA_LOCATIONS).sort();
}

/**
 * Returns array of Districts for a given state
 */
function getDistrictsForState(stateName) {
  if (!stateName || !INDIA_LOCATIONS[stateName]) return [];
  return Object.keys(INDIA_LOCATIONS[stateName]).sort();
}

/**
 * Returns array of Cities/Towns for a given state & district
 */
function getCitiesForDistrict(stateName, districtName) {
  if (!stateName || !districtName || !INDIA_LOCATIONS[stateName] || !INDIA_LOCATIONS[stateName][districtName]) return [];
  return INDIA_LOCATIONS[stateName][districtName].slice().sort();
}

/**
 * Builds a 3-tier Cascading Location Selector DOM element
 * @param {Object} options Configuration options
 * @returns {HTMLElement} Container div holding State, District, City dropdowns
 */
function createCascadingLocationSelector(options = {}) {
  const {
    idPrefix = 'loc-cascader',
    showAddButton = true,
    addButtonLabel = 'Add Location',
    onSelectLocation = null,
    selectClass = 'cc-select w-full bg-surface-container-lowest border border-glass-stroke rounded-xl px-4 py-3 text-on-surface text-sm focus:outline-none focus:border-primary',
    buttonClass = 'px-5 py-3 rounded-xl bg-primary text-on-primary font-bold text-sm hover:scale-105 transition-all shadow-md shrink-0 cursor-pointer'
  } = options;

  const wrap = document.createElement('div');
  wrap.className = options.wrapClass || (showAddButton ? 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 items-end w-full' : 'grid grid-cols-1 md:grid-cols-3 gap-2.5 items-end w-full');

  // 1. State Dropdown
  const stateCol = document.createElement('div');
  stateCol.className = 'flex flex-col gap-1 w-full min-w-0';
  stateCol.innerHTML = `
    <label for="${idPrefix}-state" class="text-xs font-bold uppercase tracking-widest text-on-surface-variant truncate">1. State / UT</label>
    <select id="${idPrefix}-state" class="${selectClass}">
      <option value="">-- Select State --</option>
      ${getIndianStates().map(s => `<option value="${s}">${s}</option>`).join('')}
    </select>
  `;

  // 2. District Dropdown
  const distCol = document.createElement('div');
  distCol.className = 'flex flex-col gap-1 w-full min-w-0';
  distCol.innerHTML = `
    <label for="${idPrefix}-district" class="text-xs font-bold uppercase tracking-widest text-on-surface-variant truncate">2. District</label>
    <select id="${idPrefix}-district" class="${selectClass}" disabled>
      <option value="">-- Select District --</option>
    </select>
  `;

  // 3. City / Area Dropdown
  const cityCol = document.createElement('div');
  cityCol.className = 'flex flex-col gap-1 w-full min-w-0';
  cityCol.innerHTML = `
    <label for="${idPrefix}-city" class="text-xs font-bold uppercase tracking-widest text-on-surface-variant truncate">3. City / Town</label>
    <select id="${idPrefix}-city" class="${selectClass}" disabled>
      <option value="">-- Select City --</option>
    </select>
  `;

  wrap.appendChild(stateCol);
  wrap.appendChild(distCol);
  wrap.appendChild(cityCol);

  if (showAddButton) {
    const btnCol = document.createElement('div');
    btnCol.className = 'flex flex-col gap-1 w-full min-w-0';
    btnCol.innerHTML = `
      <label class="text-xs font-bold uppercase tracking-widest opacity-0 select-none pointer-events-none hidden lg:block">&nbsp;</label>
      <button id="${idPrefix}-add-btn" type="button" class="${buttonClass} whitespace-nowrap w-full text-center">
        ${addButtonLabel}
      </button>
    `;
    wrap.appendChild(btnCol);
  }

  // Wire event handlers after DOM insertion
  setTimeout(() => {
    const stateEl = document.getElementById(`${idPrefix}-state`);
    const distEl  = document.getElementById(`${idPrefix}-district`);
    const cityEl  = document.getElementById(`${idPrefix}-city`);
    const addBtn  = document.getElementById(`${idPrefix}-add-btn`);

    if (stateEl && distEl && cityEl) {
      stateEl.addEventListener('change', () => {
        const state = stateEl.value;
        distEl.innerHTML = '<option value="">-- Select District --</option>';
        cityEl.innerHTML = '<option value="">-- Select City / Area --</option>';
        cityEl.disabled = true;

        if (state) {
          const districts = getDistrictsForState(state);
          districts.forEach(d => {
            distEl.innerHTML += `<option value="${d}">${d}</option>`;
          });
          distEl.disabled = false;
        } else {
          distEl.disabled = true;
        }
      });

      distEl.addEventListener('change', () => {
        const state = stateEl.value;
        const dist = distEl.value;
        cityEl.innerHTML = '<option value="">-- Select City / Area --</option>';

        if (state && dist) {
          const cities = getCitiesForDistrict(state, dist);
          cities.forEach(c => {
            cityEl.innerHTML += `<option value="${c}">${c}</option>`;
          });
          cityEl.disabled = false;
        } else {
          cityEl.disabled = true;
        }
      });

      if (addBtn) {
        addBtn.addEventListener('click', () => {
          const st = stateEl.value;
          const dt = distEl.value;
          const ct = cityEl.value;
          if (!st) { alert('Please select a State.'); return; }
          if (!dt) { alert('Please select a District.'); return; }
          if (!ct) { alert('Please select a City.'); return; }

          const formattedLocation = `${ct}, ${st}`;
          if (typeof onSelectLocation === 'function') {
            onSelectLocation(formattedLocation, { city: ct, district: dt, state: st });
          }
        });
      }
    }
  }, 50);

  return wrap;
}
