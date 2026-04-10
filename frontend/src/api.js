import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const api = axios.create({
  baseURL: API,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Intent Parsing
export const parseIntent = async (text, language = 'fr') => {
  const response = await api.post('/parse-intent', { text, language });
  return response.data;
};

// Flights
export const searchFlights = async (searchParams) => {
  const response = await api.post('/flights/search', searchParams);
  return response.data;
};

export const getFlightById = async (flightId) => {
  const response = await api.get(`/flights/${flightId}`);
  return response.data;
};

// Users
export const createUser = async (userData) => {
  const response = await api.post('/users', userData);
  return response.data;
};

export const getUserById = async (userId) => {
  const response = await api.get(`/users/${userId}`);
  return response.data;
};

export const createUsersBulk = async (usersData) => {
  const response = await api.post('/users/bulk', usersData);
  return response.data;
};

// Bookings
export const createBooking = async (bookingData) => {
  const response = await api.post('/bookings', bookingData);
  return response.data;
};

export const getUserBookings = async (userId) => {
  const response = await api.get(`/bookings/user/${userId}`);
  return response.data;
};

export const getBookingById = async (bookingId) => {
  const response = await api.get(`/bookings/${bookingId}`);
  return response.data;
};

// Payments
export const processMomoPayment = async (paymentData) => {
  const response = await api.post('/payments/momo', paymentData);
  return response.data;
};

export const processGooglePay = async (paymentData) => {
  const response = await api.post('/payments/google-pay', paymentData);
  return response.data;
};

export const processApplePay = async (paymentData) => {
  const response = await api.post('/payments/apple-pay', paymentData);
  return response.data;
};

// WhatsApp
export const sendWhatsAppTicket = async (phone, bookingId) => {
  const response = await api.post('/whatsapp/send-ticket', {
    phone_number: phone,
    booking_id: bookingId,
  });
  return response.data;
};

// Cities
export const getCities = async () => {
  const response = await api.get('/cities');
  return response.data;
};

// Health check
export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};

export default api;
