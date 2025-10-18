const parseLocalDate = (dateString) => {
    if (!dateString) return new Date();
    if (dateString instanceof Date) return dateString;

    let dateOnly;
    if (typeof dateString === 'string') {
        dateOnly = dateString.split('T')[0].split(' ')[0];
    } else {
        dateOnly = String(dateString).split('T')[0].split(' ')[0];
    }

    const [year, month, day] = dateOnly.split('-').map(Number);
    return new Date(year, month - 1, day);
};

console.log('Test 1 (2025-10-18):', parseLocalDate('2025-10-18'));
console.log('Test 2 (2025-10-18 00:00:00):', parseLocalDate('2025-10-18 00:00:00'));
console.log('Test 3 (2025-10-18T00:00:00):', parseLocalDate('2025-10-18T00:00:00'));
